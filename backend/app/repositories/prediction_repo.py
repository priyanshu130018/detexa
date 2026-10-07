"""
app/repositories/prediction_repo.py
─────────────────────────────────────────────────────────────────────────────
FraudPrediction repository for decision logs, model auditing, and overrides.
"""

from typing import List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session, joinedload

from app.db.models import DecisionType, FraudPrediction, RiskLevel
from app.repositories.base_repo import BaseRepository


class FraudPredictionRepository(BaseRepository[FraudPrediction]):
    def __init__(self, db: Session):
        super().__init__(FraudPrediction, db)

    def get_with_relations(self, pred_id: uuid.UUID) -> Optional[FraudPrediction]:
        return (
            self.db.query(FraudPrediction)
            .options(
                joinedload(FraudPrediction.transaction),
                joinedload(FraudPrediction.model),
                joinedload(FraudPrediction.alert),
            )
            .filter(FraudPrediction.id == pred_id)
            .first()
        )

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        decision: Optional[str] = None,
        risk_level: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Tuple[List[FraudPrediction], int]:
        q = self.db.query(FraudPrediction).options(
            joinedload(FraudPrediction.transaction),
            joinedload(FraudPrediction.model),
            joinedload(FraudPrediction.alert),
        )

        if decision:
            q = q.filter(FraudPrediction.decision == decision)
        if risk_level:
            q = q.filter(FraudPrediction.risk_level == risk_level)
        if endpoint:
            q = q.filter(FraudPrediction.endpoint == endpoint)
        if model_version:
            q = q.filter(FraudPrediction.model_version == model_version)

        total = q.count()
        items = q.order_by(FraudPrediction.created_at.desc()).offset(skip).limit(limit).all()
        return items, total
