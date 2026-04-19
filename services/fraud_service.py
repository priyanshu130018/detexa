"""
services/fraud_service.py
─────────────────────────────────────────────────────────────────────────────
Business-logic layer for credit-card fraud detection.
Orchestrates: model inference → risk classification → DB persistence → cache.
"""

import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from core.config import settings
from core.logging import logger
from database.models import Alert, PredictionLog, RiskLevel, Transaction
from ml.models.credit_fraud_model import CreditFraudModel


def _risk_level(score: float) -> RiskLevel:
    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH
    if score >= settings.fraud_threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class FraudDetectionService:

    def __init__(self, db: Session):
        self.db = db
        self._model = CreditFraudModel.get_instance()

    # ── Credit Fraud ──────────────────────────────────────────────────────────

    def predict_credit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()

        fraud_score, shap_features = self._model.predict(payload)
        risk = _risk_level(fraud_score)
        is_fraud = fraud_score >= settings.fraud_threshold
        latency_ms = (time.perf_counter() - t0) * 1000

        # Persist transaction
        txn_id = str(uuid.uuid4())
        txn = Transaction(
            id=uuid.UUID(txn_id),
            transaction_ref=f"TXN-{uuid.uuid4().hex[:10].upper()}",
            user_id=uuid.UUID(payload["user_id"]) if payload.get("user_id") else None,
            amount=payload.get("amount", payload.get("Amount", 0)),
            fraud_score=fraud_score,
            risk_level=risk,
            is_fraud=is_fraud,
            merchant=payload.get("merchant"),
            category=payload.get("category"),
            country=payload.get("country"),
        )
        self.db.add(txn)

        # Raise alert for medium / high risk
        if is_fraud or fraud_score > 0.4:
            alert = Alert(
                user_id=txn.user_id,
                transaction_id=txn.id,
                alert_type="credit_fraud",
                risk_level=risk,
                score=fraud_score,
                description=(
                    f"Suspicious transaction: ${txn.amount:.2f}"
                    + (f" at {txn.merchant}" if txn.merchant else "")
                ),
                shap_values=shap_features,
            )
            self.db.add(alert)

        # Audit log
        self.db.add(PredictionLog(
            endpoint="/predict/credit",
            input_hash=CreditFraudModel.hash_input(payload),
            fraud_score=fraud_score,
            risk_level=risk,
            latency_ms=latency_ms,
            model_version=CreditFraudModel.MODEL_VERSION,
        ))
        self.db.commit()

        logger.info(f"Credit predict txn={txn_id} score={fraud_score:.4f} risk={risk.value}")

        return {
            "transaction_id": txn_id,
            "fraud_score": round(fraud_score, 4),
            "risk_level": risk.value,
            "is_fraud": is_fraud,
            "shap_top_features": shap_features,
            "model_version": CreditFraudModel.MODEL_VERSION,
            "latency_ms": round(latency_ms, 2),
        }
