"""
app/services/alert_service.py
─────────────────────────────────────────────────────────────────────────────
Alert querying, status transitions with audit logging, and cached dashboard stats.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import cache_get, cache_set
from app.db.models import (
    AuditLog,
    FraudAlert,
    AlertStatus,
    RiskLevel,
    Transaction,
    User,
)
from app.models.schemas import DashboardStats


class AlertService:
    def __init__(self, db: Session):
        self.db = db

    def list_alerts(
        self,
        limit: int = 100,
        skip: int = 0,
        status_filter: Optional[str] = None,
        risk_level: Optional[str] = None,
        alert_type: Optional[str] = None,
    ) -> List[FraudAlert]:
        """Retrieve alerts joined with User, Assignee, Transaction, and Prediction."""
        q = self.db.query(FraudAlert).options(
            joinedload(FraudAlert.user),
            joinedload(FraudAlert.assignee),
            joinedload(FraudAlert.transaction),
            joinedload(FraudAlert.prediction),
        )

        if status_filter:
            q = q.filter(FraudAlert.status == status_filter)
        if risk_level:
            q = q.filter(FraudAlert.risk_level == risk_level)
        if alert_type:
            q = q.filter(FraudAlert.alert_type == alert_type)

        return (
            q.order_by(FraudAlert.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_alert_by_id(self, alert_id: uuid.UUID) -> FraudAlert:
        """Retrieve single alert with relational join."""
        alert = (
            self.db.query(FraudAlert)
            .options(
                joinedload(FraudAlert.user),
                joinedload(FraudAlert.assignee),
                joinedload(FraudAlert.transaction),
                joinedload(FraudAlert.prediction),
            )
            .filter(FraudAlert.id == alert_id)
            .first()
        )
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return alert

    def update_alert_status(
        self,
        alert_id: uuid.UUID,
        new_status: str,
        assigned_to: Optional[uuid.UUID] = None,
        resolution_notes: Optional[str] = None,
        admin_user_id: Optional[uuid.UUID] = None,
    ) -> FraudAlert:
        """Update alert lifecycle status with atomic audit log persistence."""
        alert = self.db.query(FraudAlert).filter(FraudAlert.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        try:
            enum_status = AlertStatus(new_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid alert status. Valid values: {[s.value for s in AlertStatus]}",
            )

        prev_status = alert.status.value

        try:
            alert.status = enum_status
            if enum_status == AlertStatus.RESOLVED:
                alert.resolved_at = datetime.now(timezone.utc)
            elif alert.resolved_at and enum_status != AlertStatus.RESOLVED:
                alert.resolved_at = None

            if assigned_to is not None:
                alert.assigned_to = assigned_to
            if resolution_notes is not None:
                alert.resolution_notes = resolution_notes

            # Record audit trail
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=admin_user_id or alert.user_id,
                action="ALERT_STATUS_UPDATED",
                entity_type="fraud_alert",
                entity_id=str(alert.id),
                details={
                    "previous_status": prev_status,
                    "new_status": enum_status.value,
                    "resolution_notes": resolution_notes,
                },
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(audit)
            self.db.commit()
            self.db.refresh(alert)
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Transaction rollback while updating alert {alert_id}: {exc}")
            raise HTTPException(status_code=500, detail="Database failure updating alert status")

        return alert

    def get_dashboard_stats(self) -> DashboardStats:
        from sqlalchemy import case
        cache_key = "stats:dashboard"
        cached = cache_get(cache_key)
        if cached:
            cached["cached"] = True
            return DashboardStats(**cached)

        txn_row = (
            self.db.query(
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_count"),
                func.sum(case((Transaction.risk_level == RiskLevel.HIGH, 1), else_=0)).label("high"),
                func.sum(case((Transaction.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label("medium"),
                func.sum(case((Transaction.risk_level == RiskLevel.LOW, 1), else_=0)).label("low"),
                func.avg(Transaction.fraud_score).label("avg_score"),
            ).first()
        )

        total = txn_row.total or 0 if txn_row else 0
        fraud_count = int(txn_row.fraud_count or 0) if txn_row else 0
        high = int(txn_row.high or 0) if txn_row else 0
        medium = int(txn_row.medium or 0) if txn_row else 0
        low = int(txn_row.low or 0) if txn_row else 0
        avg_score = float(txn_row.avg_score or 0.0) if txn_row else 0.0

        alert_row = (
            self.db.query(
                func.count(FraudAlert.id).label("total_alerts"),
                func.sum(case((FraudAlert.status == AlertStatus.OPEN, 1), else_=0)).label("open_alerts"),
            ).first()
        )
        total_alerts = alert_row.total_alerts or 0 if alert_row else 0
        open_alerts = int(alert_row.open_alerts or 0) if alert_row else 0

        stats = DashboardStats(
            total_transactions=total,
            fraud_count=fraud_count,
            fraud_rate=round(fraud_count / total, 4) if total else 0.0,
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            total_alerts=total_alerts,
            open_alerts=open_alerts,
            avg_fraud_score=round(avg_score, 4),
            cached=False,
        )

        cache_set(cache_key, stats.model_dump(), ttl_seconds=settings.redis_cache_ttl_stats)
        return stats
