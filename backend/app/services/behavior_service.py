"""
app/services/behavior_service.py
─────────────────────────────────────────────────────────────────────────────
Behavioral anomaly detection business logic, normalized session tracking,
and multi-table atomic transaction management.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import cache_delete_pattern
from app.db.models import (
    AuditLog,
    BehaviorLog,
    DecisionType,
    Device,
    FraudAlert,
    FraudPrediction,
    IPAddress,
    ModelMetadata,
    RiskLevel,
    AlertStatus,
)
from app.ml.models.behavior_model import BehaviorAnomalyModel


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
    return DecisionType.ALLOW


class BehaviorDetectionService:
    def __init__(self, db: Session):
        self.db = db
        self._model = BehaviorAnomalyModel.get_instance()

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
            if user_agent and not device.user_agent:
                device.user_agent = user_agent
            self.db.flush()
        return device

    def _get_or_create_ip(
        self, ip_str: Optional[str], country: Optional[str] = None, city: Optional[str] = None, is_vpn: bool = False, is_tor: bool = False
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
                is_vpn=is_vpn,
                is_tor=is_tor,
                reputation_score=0.8 if (is_tor or is_vpn) else 0.0,
                last_checked_at=datetime.now(timezone.utc),
            )
            self.db.add(ip_rec)
            self.db.flush()
        else:
            ip_rec.last_checked_at = datetime.now(timezone.utc)
            if is_vpn:
                ip_rec.is_vpn = True
            if is_tor:
                ip_rec.is_tor = True
            self.db.flush()
        return ip_rec

    def _get_or_create_model_metadata(self, version: str) -> ModelMetadata:
        model_meta = self.db.query(ModelMetadata).filter(
            ModelMetadata.model_name == "BehaviorAnomalyModel",
            ModelMetadata.version == version,
        ).first()
        if not model_meta:
            model_meta = ModelMetadata(
                id=uuid.uuid4(),
                model_name="BehaviorAnomalyModel",
                version=version,
                algorithm="Isolation Forest + Heuristic Anomaly Scoring",
                threshold=settings.fraud_threshold,
                is_active=True,
                metrics={"contamination": 0.05, "n_estimators": 100},
                trained_at=datetime.now(timezone.utc),
            )
            self.db.add(model_meta)
            self.db.flush()
        return model_meta

    def predict_behavior(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        score, latency_ms, risk_factors = self._model.predict(payload)
        risk = calculate_risk_level(score)
        decision = calculate_decision(score)
        is_anomalous = score >= settings.fraud_threshold

        user_id_val: Optional[uuid.UUID] = None
        if payload.get("user_id"):
            try:
                user_id_val = uuid.UUID(str(payload["user_id"]))
            except (ValueError, TypeError):
                user_id_val = None

        session_id = payload.get("session_id", uuid.uuid4().hex[:16])
        ip_address = payload.get("ip_address", "0.0.0.0")
        device_fingerprint = payload.get("device_fingerprint", "")
        user_agent = payload.get("user_agent", "")
        country = payload.get("geo_country", "US")
        city = payload.get("geo_city", "Unknown")
        is_vpn = payload.get("is_vpn", False)
        is_tor = payload.get("is_tor", False)

        bl_id = uuid.uuid4()

        # Atomic transaction execution
        try:
            # 1. Resolve normalized relations
            device = self._get_or_create_device(user_id_val, device_fingerprint, user_agent)
            ip_obj = self._get_or_create_ip(ip_address, country, city, is_vpn, is_tor)
            model_meta = self._get_or_create_model_metadata(BehaviorAnomalyModel.MODEL_VERSION)

            # 2. Persist behavioral session log
            bl = BehaviorLog(
                id=bl_id,
                user_id=user_id_val,
                device_id=device.id if device else None,
                ip_id=ip_obj.id if ip_obj else None,
                session_id=session_id,
                ip_address=ip_address,
                device_fingerprint=device_fingerprint,
                user_agent=user_agent,
                login_hour=payload.get("login_hour", 12),
                typing_speed=float(payload.get("typing_speed", 0.0)),
                mouse_velocity=float(payload.get("mouse_velocity", 0.0)),
                geo_country=country,
                geo_city=city,
                is_vpn=is_vpn,
                is_tor=is_tor,
                failed_logins=int(payload.get("failed_logins", 0)),
                device_change=bool(payload.get("device_change", False)),
                anomaly_score=round(score, 4),
                risk_level=risk,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(bl)
            self.db.flush()

            # 3. Persist prediction audit
            pred = FraudPrediction(
                id=uuid.uuid4(),
                transaction_id=None,
                model_id=model_meta.id,
                endpoint="/predict/behavior",
                input_hash=session_id,
                fraud_score=round(score, 4),
                anomaly_score=round(score, 4),
                risk_level=risk,
                is_fraud=is_anomalous,
                decision=decision,
                shap_values=[{"risk_factor": f} for f in risk_factors] if risk_factors else None,
                latency_ms=round(latency_ms, 2),
                model_version=BehaviorAnomalyModel.MODEL_VERSION,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(pred)
            self.db.flush()

            # 4. Raise alert if anomalous
            if is_anomalous:
                alert = FraudAlert(
                    id=uuid.uuid4(),
                    user_id=bl.user_id,
                    transaction_id=None,
                    prediction_id=pred.id,
                    alert_type="behavior_anomaly",
                    risk_level=risk,
                    score=round(score, 4),
                    description=(
                        f"Anomalous session from {country} "
                        f"({', '.join(risk_factors) if risk_factors else 'High anomaly signature'})"
                    ),
                    status=AlertStatus.OPEN,
                    metadata_={
                        "risk_factors": risk_factors,
                        "session_id": bl.session_id,
                        "decision": decision.value,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(alert)

                # 5. Security audit log
                audit = AuditLog(
                    id=uuid.uuid4(),
                    user_id=bl.user_id,
                    action="BEHAVIOR_ANOMALY_DETECTED",
                    entity_type="behavior_log",
                    entity_id=str(bl.id),
                    ip_address=ip_address,
                    details={
                        "session_id": session_id,
                        "anomaly_score": round(score, 4),
                        "risk_level": risk.value,
                        "risk_factors": risk_factors,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(audit)

            self.db.commit()

        except Exception as exc:
            self.db.rollback()
            logger.error(f"Transaction rollback during behavioral anomaly evaluation: {exc}")
            raise HTTPException(
                status_code=500,
                detail=f"Database transaction failure during behavior evaluation: {str(exc)}",
            )

        # Invalidate stats
        cache_delete_pattern("stats:*")

        return {
            "session_id": session_id,
            "anomaly_score": round(score, 4),
            "risk_level": risk.value,
            "is_anomalous": is_anomalous,
            "risk_factors": risk_factors,
            "latency_ms": round(latency_ms, 2),
        }

    def list_behavior_logs(self, limit: int = 100, skip: int = 0) -> List[BehaviorLog]:
        return (
            self.db.query(BehaviorLog)
            .options(
                joinedload(BehaviorLog.user),
                joinedload(BehaviorLog.device),
                joinedload(BehaviorLog.ip_rel),
            )
            .order_by(BehaviorLog.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_behavior_stats(self) -> Dict[str, Any]:
        total = self.db.query(func.count(BehaviorLog.id)).scalar() or 0
        high = self.db.query(func.count(BehaviorLog.id)).filter(BehaviorLog.risk_level == RiskLevel.HIGH).scalar() or 0
        med = self.db.query(func.count(BehaviorLog.id)).filter(BehaviorLog.risk_level == RiskLevel.MEDIUM).scalar() or 0
        low = self.db.query(func.count(BehaviorLog.id)).filter(BehaviorLog.risk_level == RiskLevel.LOW).scalar() or 0
        avg_score = self.db.query(func.avg(BehaviorLog.anomaly_score)).scalar() or 0.0

        return {
            "total_sessions": total,
            "high_risk_sessions": high,
            "medium_risk_sessions": med,
            "low_risk_sessions": low,
            "average_anomaly_score": round(float(avg_score), 4),
        }
