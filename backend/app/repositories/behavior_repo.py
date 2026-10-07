"""
app/repositories/behavior_repo.py
─────────────────────────────────────────────────────────────────────────────
BehaviorLog repository with joins and anomaly query filters.
"""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session, joinedload

from app.db.models import BehaviorLog, RiskLevel
from app.repositories.base_repo import BaseRepository


class BehaviorRepository(BaseRepository[BehaviorLog]):
    def __init__(self, db: Session):
        super().__init__(BehaviorLog, db)

    def get_with_relations(self, log_id: uuid.UUID) -> Optional[BehaviorLog]:
        return (
            self.db.query(BehaviorLog)
            .options(
                joinedload(BehaviorLog.user),
                joinedload(BehaviorLog.device),
                joinedload(BehaviorLog.ip_rel),
            )
            .filter(BehaviorLog.id == log_id)
            .first()
        )

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        risk_level: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        is_vpn: Optional[bool] = None,
        is_tor: Optional[bool] = None,
    ) -> Tuple[List[BehaviorLog], int]:
        q = self.db.query(BehaviorLog).options(
            joinedload(BehaviorLog.user),
            joinedload(BehaviorLog.device),
            joinedload(BehaviorLog.ip_rel),
        )

        if risk_level:
            q = q.filter(BehaviorLog.risk_level == risk_level)
        if user_id:
            q = q.filter(BehaviorLog.user_id == user_id)
        if is_vpn is not None:
            q = q.filter(BehaviorLog.is_vpn == is_vpn)
        if is_tor is not None:
            q = q.filter(BehaviorLog.is_tor == is_tor)

        total = q.count()
        items = q.order_by(BehaviorLog.created_at.desc()).offset(skip).limit(limit).all()
        return items, total
