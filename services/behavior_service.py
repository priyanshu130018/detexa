"""
services/behavior_service.py
─────────────────────────────────────────────────────────────────────────────
Business-logic layer for behavioural anomaly detection.
"""

import time
import uuid
from typing import Any, Dict

from sqlalchemy.orm import Session

from core.config import settings
from core.logging import logger
from database.models import Alert, BehaviorLog, PredictionLog, RiskLevel
from ml.models.behavior_model import BehaviorAnomalyModel


def _risk_level(score: float) -> RiskLevel:
    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH
    if score >= settings.fraud_threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class BehaviorDetectionService:

    def __init__(self, db: Session):
        self.db = db
        self._model = BehaviorAnomalyModel.get_instance()

    def predict_behavior(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        score, latency_ms = self._model.predict(payload)
        risk = _risk_level(score)
        is_anomalous = score >= settings.fraud_threshold

        # Persist log
        bl = BehaviorLog(
            id=uuid.uuid4(),
            user_id=uuid.UUID(payload["user_id"]) if payload.get("user_id") else None,
            session_id=payload.get("session_id", ""),
            ip_address=payload.get("ip_address", ""),
            device_fingerprint=payload.get("device_fingerprint", ""),
            user_agent=payload.get("user_agent", ""),
            login_hour=payload.get("login_hour", 0),
            typing_speed=payload.get("typing_speed", 0),
            mouse_velocity=payload.get("mouse_velocity", 0),
            geo_country=payload.get("geo_country", ""),
            geo_city=payload.get("geo_city", ""),
            is_vpn=payload.get("is_vpn", False),
            is_tor=payload.get("is_tor", False),
            failed_logins=payload.get("failed_logins", 0),
            device_change=payload.get("device_change", False),
            anomaly_score=score,
            risk_level=risk,
        )
        self.db.add(bl)

        if is_anomalous:
            alert = Alert(
                user_id=bl.user_id,
                alert_type="behavior_anomaly",
                risk_level=risk,
                score=score,
                description=(
                    f"Anomalous session from {payload.get('geo_country', 'unknown')}"
                    + (" via TOR" if payload.get("is_tor") else " via VPN" if payload.get("is_vpn") else "")
                ),
            )
            self.db.add(alert)

        self.db.add(PredictionLog(
            endpoint="/predict/behavior",
            input_hash="",
            anomaly_score=score,
            risk_level=risk,
            latency_ms=latency_ms,
            model_version=BehaviorAnomalyModel.MODEL_VERSION,
        ))
        self.db.commit()

        logger.info(f"Behavior predict session={bl.session_id} score={score:.4f} risk={risk.value}")

        return {
            "session_id": bl.session_id,
            "anomaly_score": round(score, 4),
            "risk_level": risk.value,
            "is_anomalous": is_anomalous,
            "latency_ms": round(latency_ms, 2),
        }
