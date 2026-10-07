"""
app/repositories/transaction_repo.py
─────────────────────────────────────────────────────────────────────────────
Transaction repository with relational SQL joins, filtering, and aggregations.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.db.models import Transaction, Merchant, User, RiskLevel
from app.repositories.base_repo import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, db: Session):
        super().__init__(Transaction, db)

    def get_with_relations(self, txn_id: uuid.UUID) -> Optional[Transaction]:
        return (
            self.db.query(Transaction)
            .options(
                joinedload(Transaction.merchant_rel),
                joinedload(Transaction.user),
                joinedload(Transaction.device),
                joinedload(Transaction.ip_rel),
                joinedload(Transaction.prediction),
                joinedload(Transaction.alert),
            )
            .filter(Transaction.id == txn_id)
            .first()
        )

    def get_by_ref(self, ref: str) -> Optional[Transaction]:
        return (
            self.db.query(Transaction)
            .options(
                joinedload(Transaction.merchant_rel),
                joinedload(Transaction.user),
                joinedload(Transaction.prediction),
                joinedload(Transaction.alert),
            )
            .filter(Transaction.transaction_ref == ref)
            .first()
        )

    def list_filtered(
        self,
        skip: int = 0,
        limit: int = 100,
        is_fraud: Optional[bool] = None,
        risk_level: Optional[str] = None,
        search: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
        merchant_id: Optional[uuid.UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> Tuple[List[Transaction], int]:
        q = self.db.query(Transaction).options(
            joinedload(Transaction.merchant_rel),
            joinedload(Transaction.user),
            joinedload(Transaction.device),
            joinedload(Transaction.ip_rel),
            joinedload(Transaction.prediction),
            joinedload(Transaction.alert),
        )

        if is_fraud is not None:
            q = q.filter(Transaction.is_fraud == is_fraud)
        if risk_level:
            q = q.filter(Transaction.risk_level == risk_level)
        if user_id:
            q = q.filter(Transaction.user_id == user_id)
        if merchant_id:
            q = q.filter(Transaction.merchant_id == merchant_id)
        if start_date:
            q = q.filter(Transaction.timestamp >= start_date)
        if end_date:
            q = q.filter(Transaction.timestamp <= end_date)
        if min_amount is not None:
            q = q.filter(Transaction.amount >= min_amount)
        if max_amount is not None:
            q = q.filter(Transaction.amount <= max_amount)

        if search:
            pattern = f"%{search}%"
            q = (
                q.outerjoin(Transaction.merchant_rel)
                .outerjoin(Transaction.user)
                .filter(
                    (Transaction.merchant.ilike(pattern))
                    | (Merchant.name.ilike(pattern))
                    | (Transaction.transaction_ref.ilike(pattern))
                    | (Transaction.category.ilike(pattern))
                    | (User.name.ilike(pattern))
                    | (User.email.ilike(pattern))
                )
            )

        total = q.count()
        items = q.order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
        return items, total

    def get_summary_stats(self) -> Dict[str, Any]:
        total = self.db.query(func.count(Transaction.id)).scalar() or 0
        fraud_count = self.db.query(func.count(Transaction.id)).filter(Transaction.is_fraud == True).scalar() or 0
        high = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.HIGH).scalar() or 0
        medium = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.MEDIUM).scalar() or 0
        low = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.LOW).scalar() or 0
        avg_score = self.db.query(func.avg(Transaction.fraud_score)).scalar() or 0.0
        total_volume = self.db.query(func.sum(Transaction.amount)).scalar() or 0.0
        fraud_volume = self.db.query(func.sum(Transaction.amount)).filter(Transaction.is_fraud == True).scalar() or 0.0

        return {
            "total_transactions": total,
            "fraud_count": fraud_count,
            "fraud_rate": round(fraud_count / total, 4) if total else 0.0,
            "high_risk_count": high,
            "medium_risk_count": medium,
            "low_risk_count": low,
            "avg_fraud_score": round(float(avg_score), 4),
            "total_volume": round(float(total_volume), 2),
            "fraud_volume": round(float(fraud_volume), 2),
        }
