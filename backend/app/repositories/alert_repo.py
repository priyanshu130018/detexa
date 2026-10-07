"""
app/repositories/alert_repo.py
─────────────────────────────────────────────────────────────────────────────
FraudAlert repository with joins, filtering, status transitions, and triage metrics.
"""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models import AlertStatus, FraudAlert, RiskLevel
from app.repositories.base_repo import BaseRepository


class FraudAlertRepository(BaseRepository[FraudAlert]):
    def __init__(self, db: Session):
        super().__init__(FraudAlert, db)

    def get_with_relations(self, alert_id: uuid.UUID) -> Optional[FraudAlert]:
        return (
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

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        risk_level: Optional[str] = None,
        alert_type: Optional[str] = None,
        assigned_to: Optional[uuid.UUID] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[FraudAlert], int]:
        q = self.db.query(FraudAlert).options(
            joinedload(FraudAlert.user),
            joinedload(FraudAlert.assignee),
            joinedload(FraudAlert.transaction),
            joinedload(FraudAlert.prediction),
        )

        if status:
            q = q.filter(FraudAlert.status == status)
        if risk_level:
            q = q.filter(FraudAlert.risk_level == risk_level)
        if alert_type:
            q = q.filter(FraudAlert.alert_type == alert_type)
        if assigned_to:
            q = q.filter(FraudAlert.assigned_to == assigned_to)
        if user_id:
            q = q.filter(FraudAlert.user_id == user_id)

        total = q.count()
        items = q.order_by(FraudAlert.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def count_by_status(self, status_val: AlertStatus) -> int:
        return self.db.query(func.count(FraudAlert.id)).filter(FraudAlert.status == status_val).scalar() or 0
