"""
app/streaming/flink_processor.py
─────────────────────────────────────────────────────────────────────────────
Real-Time Stream Processing Engine (Apache Flink Architecture).
Performs stateful window feature aggregation, ML fraud inference, multi-tier
decisioning, idempotent PostgreSQL persistence, and Kafka event egress.
"""

from collections import defaultdict, deque
from datetime import datetime, timezone
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.models import (
    AlertStatus,
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
)
from app.db.session import SessionLocal
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.streaming.decision_engine import RealTimeDecisionEngine
from app.streaming.event_schemas import (
    AggregatedFeatures,
    EventHeader,
    EventType,
    FraudAlertEvent,
    ScoredTransactionEvent,
    TransactionIngestionEvent,
    TransactionPayload,
)
from app.streaming.kafka_producer import KafkaEventProducer


class SlidingWindowState:
    """
    In-memory stateful sliding window manager tracking transaction velocity,
    rolling monetary volume, and behavioral consistency per card/user.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Mapping: user_id/card_key -> deque of (timestamp, amount, merchant, device_fp, country)
        self._history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

    def record_and_compute(
        self,
        key: str,
        amount: float,
        merchant: str,
        country: str,
        device_fp: Optional[str],
        now_ts: float,
    ) -> AggregatedFeatures:
        with self._lock:
            q = self._history[key]
            # Prune records older than 1 hour (3600 seconds)
            while q and (now_ts - q[0]["ts"]) > 3600:
                q.popleft()

            # Append current
            current_entry = {
                "ts": now_ts,
                "amount": amount,
                "merchant": merchant,
                "country": country,
                "device_fp": device_fp,
            }
            q.append(current_entry)

            # Compute window metrics
            v_1m = sum(1 for item in q if (now_ts - item["ts"]) <= 60)
            v_5m = sum(1 for item in q if (now_ts - item["ts"]) <= 300)
            v_1h = len(q)

            amounts_1h = [item["amount"] for item in q]
            rolling_amt_1h = sum(amounts_1h)
            avg_amt_1h = rolling_amt_1h / len(amounts_1h) if amounts_1h else amount

            deviation_ratio = (amount / avg_amt_1h) if avg_amt_1h > 0 else 1.0
            distinct_merchants = len(set(item["merchant"] for item in q))

            # Foreign mismatch check (e.g. if previous transactions were in US and now in RU/CN)
            prev_countries = set(item["country"] for item in q if item != current_entry)
            is_foreign = bool(prev_countries and country not in prev_countries)

            # Unrecognized device check
            prev_devices = set(item["device_fp"] for item in q if item["device_fp"] and item != current_entry)
            is_new_dev = bool(prev_devices and device_fp and device_fp not in prev_devices)

            return AggregatedFeatures(
                velocity_1m=v_1m,
                velocity_5m=v_5m,
                velocity_1h=v_1h,
                rolling_amount_1h=round(rolling_amt_1h, 2),
                avg_amount_1h=round(avg_amt_1h, 2),
                amount_deviation_ratio=round(deviation_ratio, 2),
                distinct_merchants_1h=distinct_merchants,
                is_foreign_transaction=is_foreign,
                is_new_device=is_new_dev,
            )


class FlinkRealTimeStreamProcessor:
    """
    Core stream processing coordinator simulating Flink stream execution.
    Handles: Ingestion -> Stateful Windowing -> ML Inference -> Decisioning -> PostgreSQL -> Kafka Egress.
    """

    _instance: Optional["FlinkRealTimeStreamProcessor"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.window_state = SlidingWindowState()
        self.decision_engine = RealTimeDecisionEngine()
        self.ml_model = CreditFraudModel.get_instance()
        self.producer = KafkaEventProducer.get_instance()

    @classmethod
    def get_instance(cls) -> "FlinkRealTimeStreamProcessor":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def process_transaction_event(
        self,
        event: TransactionIngestionEvent,
        db: Optional[Session] = None,
    ) -> ScoredTransactionEvent:
        """
        Process a single streaming transaction event with end-to-end idempotency.
        """
        t0 = time.perf_counter()
        payload = event.payload
        user_key = payload.user_id or payload.transaction_ref
        now_ts = time.time()

        # 1. Stateful Window Feature Processing (Flink Sliding Windows)
        agg_features = self.window_state.record_and_compute(
            key=user_key,
            amount=payload.amount,
            merchant=payload.merchant,
            country=payload.country,
            device_fp=payload.device_fingerprint,
            now_ts=now_ts,
        )

        # 2. Real-Time Machine Learning Inference (XGBoost Pipeline)
        raw_dict = payload.model_dump()
        ml_fraud_score, shap_drivers = self.ml_model.predict(raw_dict)

        # 3. Real-Time Decision Engine Evaluation
        decision, risk_level, reason_codes = self.decision_engine.evaluate(
            payload=payload,
            features=agg_features,
            ml_fraud_score=ml_fraud_score,
            is_tor=False,
            is_vpn=False,
        )

        latency_ms = (time.perf_counter() - t0) * 1000

        # 4. Idempotent PostgreSQL Persistence
        db_session = db or SessionLocal()
        should_close_db = db is None

        try:
            self._persist_idempotent_records(
                db=db_session,
                payload=payload,
                agg_features=agg_features,
                fraud_score=ml_fraud_score,
                risk_level=risk_level,
                decision=decision,
                reason_codes=reason_codes,
                shap_drivers=shap_drivers,
                latency_ms=latency_ms,
                idempotency_key=event.header.idempotency_key,
            )
        except Exception as exc:
            logger.error(f"PostgreSQL persistence failed for transaction {payload.transaction_ref}: {exc}")
        finally:
            if should_close_db:
                db_session.close()

        # 5. Outbound Kafka Event Egress
        scored_header = EventHeader(
            event_id=str(uuid.uuid4()),
            idempotency_key=event.header.idempotency_key,
            event_type=EventType.TRANSACTION_SCORED,
            source="detexa-flink-stream-processor",
            partition_key=user_key,
        )

        scored_event = ScoredTransactionEvent(
            header=scored_header,
            payload=payload,
            streaming_features=agg_features,
            fraud_score=round(ml_fraud_score, 4),
            risk_level=risk_level.value,
            decision=decision.value,
            reason_codes=reason_codes,
            shap_top_features=shap_drivers,
            latency_ms=round(latency_ms, 2),
            model_version=CreditFraudModel.MODEL_VERSION,
        )

        # Publish to scored transactions stream
        self.producer.send_scored_event(scored_event)

        # If high/medium risk or blocked, publish alert event
        if decision != DecisionType.ALLOW or ml_fraud_score >= settings.fraud_threshold:
            alert_header = EventHeader(
                event_id=str(uuid.uuid4()),
                idempotency_key=event.header.idempotency_key,
                event_type=EventType.ALERT_GENERATED,
                source="detexa-flink-stream-processor",
                partition_key=user_key,
            )
            alert_event = FraudAlertEvent(
                header=alert_header,
                alert_id=str(uuid.uuid4()),
                transaction_id=payload.transaction_ref,
                transaction_ref=payload.transaction_ref,
                user_id=payload.user_id,
                score=round(ml_fraud_score, 4),
                risk_level=risk_level.value,
                decision=decision.value,
                description=(
                    f"Real-time {decision.value} alert on ${payload.amount:.2f} at {payload.merchant} "
                    f"[Score: {ml_fraud_score:.2f}, Velocity (1m): {agg_features.velocity_1m}]"
                ),
                reason_codes=reason_codes,
                shap_drivers=shap_drivers,
            )
            self.producer.send_alert_event(alert_event)

        # 6. Real-Time Event Dispatch to UI (WebSocket & SSE Streams)
        try:
            from app.core.realtime_broadcaster import RealtimeBroadcaster
            broadcaster = RealtimeBroadcaster.get_instance()
            broadcaster.push_new_transaction({
                "id": str(uuid.uuid4()),
                "transaction_ref": payload.transaction_ref,
                "amount": payload.amount,
                "merchant": payload.merchant,
                "category": payload.category,
                "country": payload.country,
                "currency": payload.currency,
                "fraud_score": round(ml_fraud_score, 4),
                "risk_level": risk_level.value,
                "decision": decision.value,
                "is_fraud": (decision == DecisionType.BLOCK or ml_fraud_score >= settings.fraud_threshold),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if decision != DecisionType.ALLOW or ml_fraud_score >= settings.fraud_threshold:
                broadcaster.push_fraud_alert({
                    "id": str(uuid.uuid4()),
                    "transaction_ref": payload.transaction_ref,
                    "alert_type": "stream_fraud",
                    "risk_level": risk_level.value,
                    "score": round(ml_fraud_score, 4),
                    "description": f"Real-time {decision.value} alert on ${payload.amount:.2f} at {payload.merchant}",
                    "status": "open",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
        except Exception as exc:
            logger.debug(f"Realtime broadcaster dispatch error: {exc}")

        return scored_event

    def _persist_idempotent_records(
        self,
        db: Session,
        payload: TransactionPayload,
        agg_features: AggregatedFeatures,
        fraud_score: float,
        risk_level: RiskLevel,
        decision: DecisionType,
        reason_codes: List[str],
        shap_drivers: Optional[List[Dict[str, Any]]],
        latency_ms: float,
        idempotency_key: str,
    ):
        """
        Guarantees idempotent persistence into normalized PostgreSQL tables.
        """
        # Idempotency check: if transaction_ref already committed, skip duplicate insert
        existing_txn = (
            db.query(Transaction)
            .filter(Transaction.transaction_ref == payload.transaction_ref)
            .first()
        )
        if existing_txn:
            logger.info(f"Idempotent skip: Transaction '{payload.transaction_ref}' already exists in PostgreSQL.")
            return

        user_id_val: Optional[uuid.UUID] = None
        if payload.user_id:
            try:
                user_id_val = uuid.UUID(str(payload.user_id))
            except ValueError:
                pass

        try:
            # 1. Merchant Resolution
            merchant = db.query(Merchant).filter(Merchant.name == payload.merchant).first()
            if not merchant:
                merchant = Merchant(
                    id=uuid.uuid4(),
                    name=payload.merchant,
                    category=payload.category,
                    risk_score=0.0,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(merchant)
                db.flush()

            # 2. Device Resolution
            device = None
            if payload.device_fingerprint:
                device = db.query(Device).filter(Device.device_fingerprint == payload.device_fingerprint).first()
                if not device:
                    device = Device(
                        id=uuid.uuid4(),
                        user_id=user_id_val,
                        device_fingerprint=payload.device_fingerprint,
                        user_agent=payload.user_agent,
                        is_trusted=not agg_features.is_new_device,
                        first_seen_at=datetime.now(timezone.utc),
                        last_seen_at=datetime.now(timezone.utc),
                    )
                    db.add(device)
                    db.flush()

            # 3. IP Resolution
            ip_obj = None
            if payload.ip_address and payload.ip_address not in ("0.0.0.0", ""):
                ip_obj = db.query(IPAddress).filter(IPAddress.ip_address == payload.ip_address).first()
                if not ip_obj:
                    ip_obj = IPAddress(
                        id=uuid.uuid4(),
                        ip_address=payload.ip_address,
                        geo_country=payload.country,
                        reputation_score=0.0,
                        last_checked_at=datetime.now(timezone.utc),
                    )
                    db.add(ip_obj)
                    db.flush()

            # 4. Insert Transaction
            txn = Transaction(
                id=uuid.uuid4(),
                user_id=user_id_val,
                customer_id=getattr(payload, "customer_id", None) or (str(user_id_val) if user_id_val else None),
                merchant_id=merchant.id,
                device_id=device.id if device else None,
                ip_id=ip_obj.id if ip_obj else None,
                transaction_ref=payload.transaction_ref,
                amount=payload.amount,
                transaction_amount=payload.amount,
                currency=payload.currency,
                merchant=merchant.name,
                category=merchant.category,
                merchant_category=getattr(payload, "merchant_category", payload.category),
                country=payload.country,
                account_type=getattr(payload, "account_type", "Savings"),
                transaction_type=getattr(payload, "transaction_type", "UPI"),
                transaction_direction=getattr(payload, "transaction_direction", "Debit"),
                account_balance=getattr(payload, "account_balance", 50000.0),
                state=getattr(payload, "state", "Maharashtra"),
                credit_score=getattr(payload, "credit_score", 650),
                has_loan=getattr(payload, "has_loan", 0),
                loan_type=getattr(payload, "loan_type", "None"),
                emi_amount=getattr(payload, "emi_amount", 0.0),
                transaction_status=getattr(payload, "transaction_status", "Success"),
                channel=getattr(payload, "channel", "Mobile_App"),
                kyc_status=getattr(payload, "kyc_status", "Verified"),
                transaction_hour=getattr(payload, "transaction_hour", 12),
                transaction_date=getattr(payload, "transaction_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                transaction_time=getattr(payload, "transaction_time", datetime.now(timezone.utc).strftime("%H:%M")),
                fraud_score=round(fraud_score, 4),
                risk_level=risk_level,
                is_fraud=(decision == DecisionType.BLOCK or fraud_score >= settings.fraud_threshold),
                label=int(decision == DecisionType.BLOCK),
                timestamp=datetime.now(timezone.utc),
            )

            db.add(txn)
            db.flush()

            # 5. Insert Prediction Log
            pred = FraudPrediction(
                id=uuid.uuid4(),
                transaction_id=txn.id,
                endpoint="/transactions/stream",
                input_hash=idempotency_key,
                fraud_score=round(fraud_score, 4),
                anomaly_score=None,
                risk_level=risk_level,
                is_fraud=txn.is_fraud,
                decision=decision,
                shap_values=shap_drivers,
                latency_ms=round(latency_ms, 2),
                model_version=BankingFraudModel.MODEL_VERSION,
                created_at=datetime.now(timezone.utc),
            )
            db.add(pred)
            db.flush()

            # 6. Conditionally Insert Alert
            if decision != DecisionType.ALLOW or fraud_score >= settings.fraud_threshold:
                alert = FraudAlert(
                    id=uuid.uuid4(),
                    user_id=txn.user_id,
                    transaction_id=txn.id,
                    prediction_id=pred.id,
                    alert_type="realtime_stream_fraud",
                    risk_level=risk_level,
                    score=round(fraud_score, 4),
                    description=(
                        f"Real-time stream alert on ${payload.amount:.2f} at {merchant.name} "
                        f"[Decision: {decision.value}, Triggers: {', '.join(reason_codes)}]"
                    ),
                    status=AlertStatus.OPEN,
                    shap_values=shap_drivers,
                    metadata_={
                        "streaming_features": agg_features.model_dump(),
                        "reason_codes": reason_codes,
                        "idempotency_key": idempotency_key,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                db.add(alert)

            # 7. Insert Audit Trail
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=txn.user_id,
                action="STREAM_TRANSACTION_EVALUATED",
                entity_type="transaction",
                entity_id=str(txn.id),
                ip_address=payload.ip_address,
                details={
                    "transaction_ref": payload.transaction_ref,
                    "decision": decision.value,
                    "risk_level": risk_level.value,
                    "fraud_score": round(fraud_score, 4),
                    "reason_codes": reason_codes,
                },
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit)

            db.commit()

        except Exception as exc:
            db.rollback()
            raise exc
