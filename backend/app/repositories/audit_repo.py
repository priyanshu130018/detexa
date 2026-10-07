"""
app/repositories/audit_repo.py
─────────────────────────────────────────────────────────────────────────────
AuditLog repository for compliance, security tracking, and forensic inspection.
"""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session, joinedload

from app.db.models import AuditLog
from app.repositories.base_repo import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    def __init__(self, db: Session):
        super().__init__(AuditLog, db)

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        entity_type: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[AuditLog], int]:
        q = self.db.query(AuditLog).options(joinedload(AuditLog.user))

        if action:
            q = q.filter(AuditLog.action == action)
        if entity_type:
            q = q.filter(AuditLog.entity_type == entity_type)
        if user_id:
            q = q.filter(AuditLog.user_id == user_id)

        total = q.count()
        items = q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
        return items, total
