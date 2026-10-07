"""
app/services/fraud_service.py
─────────────────────────────────────────────────────────────────────────────
Indian Banking Transaction Fraud prediction orchestration, risk scoring,
normalized persistence, and multi-table atomic transaction management.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import cache_get, cache_set, cache_delete_pattern
from app.decision import DecisionContext, get_decision_engine, PostgresDecisionStorage
from app.feature_store import get_feature_store
from app.graph import get_graph_service
from app.services.explanation_service import get_explanation_service
from app.db.models import (
    AuditLog,
    DecisionType,
    Device,
    FraudAlert,
    FraudPrediction,
    IPAddress,
    Merchant,
    ModelMetadata,
    RiskLevel,
    Transaction,
    AlertStatus,
)
from app.ml.models.banking_fraud_model import BankingFraudModel, CreditFraudModel


def calculate_risk_level(score: float) -> RiskLevel:
    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH
    if score >= settings.fraud_threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def calculate_decision(score: float) -> DecisionType:
    if score >= settings.high_risk_threshold:
        return DecisionType.BLOCK
    if score >= settings.fraud_threshold:
        return DecisionType.REVIEW
    if score >= settings.decision_threshold_allow:
        return DecisionType.CHALLENGE
    return DecisionType.ALLOW


class FraudDetectionService:
    def __init__(self, db: Session):
        self.db = db
        self._model = BankingFraudModel.get_instance()

    def _get_or_create_merchant(self, name: str, category: str = "Retail") -> Merchant:
        merchant = self.db.query(Merchant).filter(Merchant.name == name).first()
        if not merchant:
            merchant = Merchant(
                id=uuid.uuid4(),
                name=name,
                category=category,
                risk_score=0.0,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(merchant)
            self.db.flush()
        return merchant

    def _get_or_create_device(
        self, user_id: Optional[uuid.UUID], fingerprint: Optional[str], user_agent: Optional[str] = None
    ) -> Optional[Device]:
        if not fingerprint:
            return None
        q = self.db.query(Device).filter(Device.device_fingerprint == fingerprint)
        if user_id:
            q = q.filter(Device.user_id == user_id)
        device = q.first()
        if not device:
            device = Device(
                id=uuid.uuid4(),
                user_id=user_id,
                device_fingerprint=fingerprint,
                user_agent=user_agent,
                is_trusted=True,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
            )
            self.db.add(device)
            self.db.flush()
        else:
            device.last_seen_at = datetime.now(timezone.utc)
            self.db.flush()
        return device

    def _get_or_create_ip(
        self, ip_str: Optional[str], country: Optional[str] = None, city: Optional[str] = None
    ) -> Optional[IPAddress]:
        if not ip_str or ip_str in ("0.0.0.0", ""):
            return None
        ip_rec = self.db.query(IPAddress).filter(IPAddress.ip_address == ip_str).first()
        if not ip_rec:
            ip_rec = IPAddress(
                id=uuid.uuid4(),
                ip_address=ip_str,
                geo_country=country,
                geo_city=city,
                is_vpn=False,
                is_tor=False,
                reputation_score=0.0,
                last_checked_at=datetime.now(timezone.utc),
            )
            self.db.add(ip_rec)
            self.db.flush()
        return ip_rec

    def _get_or_create_model_metadata(self, version: str) -> ModelMetadata:
        model_meta = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == "IndianBankingFraudXGBoost",
            ModelMetadata.version == version,
        ).first()
        if not model_meta:
            model_meta = ModelMetadata(
                id=uuid.uuid4(),
                model_name="IndianBankingFraudXGBoost",
                version=version,
                algorithm="XGBoost Classifier (Indian Banking Dataset)",
                threshold=settings.fraud_threshold,
                is_active=True,
                metrics={"auc_roc": 0.54, "auc_pr": 0.02, "f1_score": 0.08},
                trained_at=datetime.now(timezone.utc),
            )
            self.db.add(model_meta)
            self.db.flush()
        return model_meta

    def predict_banking(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes end-to-end banking fraud scoring, decisioning, and PostgreSQL persistence.
        """
        t0 = time.perf_counter()
        input_hash = BankingFraudModel.hash_input(payload)

        # Check Redis cache
        cached_result = cache_get(f"pred:banking:{input_hash}")
        if cached_result:
            logger.debug(f"Redis cache hit for prediction {input_hash[:8]}")
            return cached_result

        raw_amt = payload.get("transaction_amount") or payload.get("amount") or payload.get("Amount") or 1.0
        amt_val = float(raw_amt)
        
        customer_id_str = str(payload.get("customer_id", payload.get("user_id", ""))) if (payload.get("customer_id") or payload.get("user_id")) else None
        user_id_str = str(payload.get("user_id", "")) if payload.get("user_id") else None
        merchant_name = payload.get("merchant", "Online Merchant")
        category_name = payload.get("merchant_category", payload.get("category", "Retail"))
        country_name = payload.get("country", "IN")
        device_fp = payload.get("device_fingerprint")
        user_agent_str = payload.get("user_agent")
        ip_addr_str = payload.get("ip_address")

        # 1. Fetch Real-time Sliding Window Features (Redis) & Graph Risk (Neo4j)
        user_key = customer_id_str or user_id_str or f"CUST-{uuid.uuid4().hex[:8].upper()}"
        fs = get_feature_store()
        redis_hot = fs.get_hot_features(
            user_key=user_key,
            current_amount=amt_val,
            current_merchant=merchant_name,
            current_category=category_name,
            current_device=device_fp,
            current_ip=ip_addr_str,
            current_country=country_name,
        )
        gs = get_graph_service()
        graph_risk = gs.get_features(
            user_id=user_key,
            current_device_fp=device_fp,
            current_ip=ip_addr_str,
        )

        # 2. Low-Latency ML Model Scoring with TreeSHAP
        fraud_score, shap_features = self._model.predict(payload)

        # 3. Decision Engine Policy Evaluation
        txn_id = uuid.uuid4()
        txn_ref = payload.get("transaction_id") or f"TXN-{uuid.uuid4().hex[:10].upper()}"

        ctx = DecisionContext(
            fraud_score=fraud_score,
            amount=amt_val,
            currency=payload.get("currency", "INR"),
            merchant=merchant_name,
            category=category_name,
            country=country_name,
            user_id=user_key,
            transaction_ref=txn_ref,
            device_fingerprint=device_fp,
            ip_address=ip_addr_str,
            realtime_features=redis_hot.to_dict(),
            graph_risk=graph_risk.to_dict(),
        )

        decision_outcome = get_decision_engine().evaluate(ctx)
        latency_ms = (time.perf_counter() - t0) * 1000

        user_id_val: Optional[uuid.UUID] = None
        if user_id_str:
            try:
                user_id_val = uuid.UUID(user_id_str)
            except (ValueError, TypeError):
                user_id_val = None

        # 4. Execute atomic multi-table transaction in PostgreSQL
        try:
            merchant = self._get_or_create_merchant(merchant_name, category_name)
            device = self._get_or_create_device(user_id_val, device_fp, user_agent_str)
            ip_obj = self._get_or_create_ip(ip_addr_str, country_name)

            txn = Transaction(
                id=txn_id,
                transaction_ref=txn_ref,
                customer_id=customer_id_str,
                user_id=user_id_val,
                merchant_id=merchant.id,
                device_id=device.id if device else None,
                ip_id=ip_obj.id if ip_obj else None,
                amount=amt_val,
                transaction_amount=amt_val,
                currency=payload.get("currency", "INR"),
                merchant=merchant.name,
                category=category_name,
                merchant_category=category_name,
                country=country_name,
                account_type=str(payload.get("account_type", "Savings")),
                transaction_type=str(payload.get("transaction_type", "UPI")),
                transaction_direction=str(payload.get("transaction_direction", "Debit")),
                account_balance=float(payload.get("account_balance", 50000.0)),
                state=str(payload.get("state", "Maharashtra")),
                credit_score=int(payload.get("credit_score", 650)),
                has_loan=int(payload.get("has_loan", 0)),
                loan_type=str(payload.get("loan_type", "None")),
                emi_amount=float(payload.get("emi_amount", 0.0)),
                transaction_status=str(payload.get("transaction_status", "Success")),
                channel=str(payload.get("channel", "Mobile_App")),
                kyc_status=str(payload.get("kyc_status", "Verified")),
                transaction_hour=int(payload.get("transaction_hour", 12)) if payload.get("transaction_hour") is not None else 12,
                transaction_date=str(payload.get("transaction_date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))),
                transaction_time=str(payload.get("transaction_time", datetime.now(timezone.utc).strftime("%H:%M"))),
                fraud_score=round(fraud_score, 4),
                risk_level=RiskLevel(decision_outcome.risk_level),
                is_fraud=(decision_outcome.decision.value == "BLOCK"),
                label=int(decision_outcome.decision.value == "BLOCK"),
                timestamp=datetime.now(timezone.utc),
            )

            self.db.add(txn)
            self.db.flush()

            # 3.5 Generate AI/SHAP natural language fraud explanation
            explanation = get_explanation_service().generate_explanation(
                fraud_score=fraud_score,
                risk_level=decision_outcome.risk_level,
                decision=decision_outcome.decision.value,
                shap_features=shap_features,
                transaction_data=payload,
            )

            # Persist Decision, Prediction audit, and Alerts
            PostgresDecisionStorage.persist_decision(
                db=self.db,
                outcome=decision_outcome,
                txn=txn,
                endpoint="/api/v1/predict/transaction",
                input_hash=input_hash,
                latency_ms=latency_ms,
                shap_drivers=shap_features[:settings.shap_top_k_features] if shap_features else None,
                explanation=explanation,
                model_version=BankingFraudModel.MODEL_VERSION,
            )

            self.db.commit()

        except Exception as exc:
            self.db.rollback()
            logger.error(f"Transaction rollback during banking fraud evaluation: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Database transaction failure during fraud evaluation: {str(exc)}",
            )

        # Invalidate dashboard stats cache
        cache_delete_pattern("stats:*")

        # Ingest into Redis Feature Store for real-time sliding window calculations
        try:
            fs = get_feature_store()
            fs.ingest_transaction(
                user_key=user_key,
                amount=txn.amount,
                merchant=merchant.name,
                category=merchant.category,
                country=country_name,
                device_fingerprint=device_fp,
                ip_address=ip_addr_str,
                is_failed=(payload.get("transaction_status") == "Failed"),
            )
            fs.record_risk_decision(
                user_key=user_key,
                risk_level=decision_outcome.risk_level,
                decision=decision_outcome.decision.value,
            )
        except Exception as fs_exc:
            logger.debug(f"Non-critical feature store ingestion error: {fs_exc}")

        # Ingest into Neo4j Graph Database
        try:
            gs = get_graph_service()
            gs.sync_transaction(
                user_id=user_key,
                transaction_ref=txn_ref,
                amount=txn.amount,
                currency=txn.currency,
                merchant_name=merchant.name,
                merchant_category=merchant.category,
                device_fingerprint=device_fp,
                ip_address=ip_addr_str,
                country=country_name,
                fraud_score=round(fraud_score, 4),
                risk_level=decision_outcome.risk_level,
                decision=decision_outcome.decision.value,
                is_fraud=(decision_outcome.decision.value == "BLOCK"),
            )
        except Exception as gs_exc:
            logger.debug(f"Non-critical graph sync error: {gs_exc}")

        response_payload = {
            "transaction_id": str(txn_id),
            "transaction_ref": txn_ref,
            "fraud_score": round(fraud_score, 4),
            "risk_level": decision_outcome.risk_level,
            "decision": decision_outcome.decision.value,
            "is_fraud": (decision_outcome.decision.value == "BLOCK"),
            "primary_reason": decision_outcome.primary_reason,
            "reason_codes": decision_outcome.reason_codes,
            "requires_step_up_auth": decision_outcome.requires_step_up_auth,
            "shap_top_features": shap_features[:settings.shap_top_k_features] if shap_features else None,
            "explanation": explanation,
            "model_version": BankingFraudModel.MODEL_VERSION,
            "latency_ms": round(latency_ms, 2),
        }

        # Cache response in Redis
        cache_set(f"pred:banking:{input_hash}", response_payload, ttl_seconds=settings.redis_cache_ttl_predictions)

        return response_payload

    # Backward compatibility alias
    predict_credit = predict_banking

    def predict_batch(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(payloads) > settings.batch_inference_max_rows:
            raise HTTPException(
                status_code=400,
                detail=f"Batch size {len(payloads)} exceeds maximum allowed {settings.batch_inference_max_rows} rows",
            )

        t0 = time.perf_counter()
        results = []
        fraud_count = 0

        for item in payloads:
            res = self.predict_banking(item)
            if res["is_fraud"]:
                fraud_count += 1
            results.append(res)

        total_latency = (time.perf_counter() - t0) * 1000

        return {
            "total_processed": len(payloads),
            "fraud_detected_count": fraud_count,
            "predictions": results,
            "batch_latency_ms": round(total_latency, 2),
        }
