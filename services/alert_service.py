"""
services/alert_service.py
─────────────────────────────────────────────────────────────────────────────
CRUD helpers for alerts and dashboard statistics.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Alert, AlertStatus, RiskLevel, Transaction
from models.schemas import DashboardStats


class AlertService:

    def __init__(self, db: Session):
        self.db = db

    # ── Alerts ────────────────────────────────────────────────────────────────

    def list_alerts(
        self,
        limit: int = 100,
        skip: int = 0,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> List[Alert]:
        q = self.db.query(Alert)
        if status:
            q = q.filter(Alert.status == status)
        if risk_level:
            q = q.filter(Alert.risk_level == risk_level)
        return q.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()

    def update_alert_status(self, alert_id: str, new_status: str) -> Alert:
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.status = new_status
        if new_status == AlertStatus.RESOLVED:
            alert.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    # ── Dashboard Stats ───────────────────────────────────────────────────────

    def get_dashboard_stats(self) -> DashboardStats:
        total = self.db.query(func.count(Transaction.id)).scalar() or 0
        fraud_count = self.db.query(func.count(Transaction.id)).filter(
            Transaction.is_fraud == True
        ).scalar() or 0

        high = self.db.query(func.count(Transaction.id)).filter(
            Transaction.risk_level == RiskLevel.HIGH
        ).scalar() or 0
        medium = self.db.query(func.count(Transaction.id)).filter(
            Transaction.risk_level == RiskLevel.MEDIUM
        ).scalar() or 0
        low = self.db.query(func.count(Transaction.id)).filter(
            Transaction.risk_level == RiskLevel.LOW
        ).scalar() or 0

        total_alerts = self.db.query(func.count(Alert.id)).scalar() or 0
        open_alerts = self.db.query(func.count(Alert.id)).filter(
            Alert.status == AlertStatus.OPEN
        ).scalar() or 0

        avg_score = self.db.query(func.avg(Transaction.fraud_score)).scalar() or 0.0

        return DashboardStats(
            total_transactions=total,
            fraud_count=fraud_count,
            fraud_rate=round(fraud_count / total, 4) if total else 0.0,
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            total_alerts=total_alerts,
            open_alerts=open_alerts,
            avg_fraud_score=round(float(avg_score), 4),
        )

    # ── Transaction list ──────────────────────────────────────────────────────

    def list_transactions(
        self,
        limit: int = 200,
        skip: int = 0,
        is_fraud: Optional[bool] = None,
    ) -> List[Transaction]:
        q = self.db.query(Transaction)
        if is_fraud is not None:
            q = q.filter(Transaction.is_fraud == is_fraud)
        return q.order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
