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
        base_q = self.db.query(Transaction.id)

        if is_fraud is not None:
            base_q = base_q.filter(Transaction.is_fraud == is_fraud)
        if risk_level:
            base_q = base_q.filter(Transaction.risk_level == risk_level)
        if user_id:
            base_q = base_q.filter(Transaction.user_id == user_id)
        if merchant_id:
            base_q = base_q.filter(Transaction.merchant_id == merchant_id)
        if start_date:
            base_q = base_q.filter(Transaction.timestamp >= start_date)
        if end_date:
            base_q = base_q.filter(Transaction.timestamp <= end_date)
        if min_amount is not None:
            base_q = base_q.filter(Transaction.amount >= min_amount)
        if max_amount is not None:
            base_q = base_q.filter(Transaction.amount <= max_amount)

        if search:
            pattern = f"%{search}%"
            base_q = (
                base_q.outerjoin(Transaction.merchant_rel)
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

        total = base_q.count()

        q = self.db.query(Transaction)

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

        items = q.order_by(Transaction.timestamp.desc()).offset(skip).limit(limit).all()
        return items, total

    def get_summary_stats(self) -> Dict[str, Any]:
        from sqlalchemy import case
        row = (
            self.db.query(
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_count"),
                func.sum(case((Transaction.risk_level == RiskLevel.HIGH, 1), else_=0)).label("high"),
                func.sum(case((Transaction.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label("medium"),
                func.sum(case((Transaction.risk_level == RiskLevel.LOW, 1), else_=0)).label("low"),
                func.avg(Transaction.fraud_score).label("avg_score"),
                func.sum(Transaction.amount).label("total_volume"),
                func.sum(case((Transaction.is_fraud == True, Transaction.amount), else_=0.0)).label("fraud_volume"),
            ).first()
        )

        total = row.total or 0 if row else 0
        fraud_count = int(row.fraud_count or 0) if row else 0
        high = int(row.high or 0) if row else 0
        medium = int(row.medium or 0) if row else 0
        low = int(row.low or 0) if row else 0
        avg_score = float(row.avg_score or 0.0) if row else 0.0
        total_volume = float(row.total_volume or 0.0) if row else 0.0
        fraud_volume = float(row.fraud_volume or 0.0) if row else 0.0

        return {
            "total_transactions": total,
            "fraud_count": fraud_count,
            "fraud_rate": round(fraud_count / total, 4) if total else 0.0,
            "high_risk_count": high,
            "medium_risk_count": medium,
            "low_risk_count": low,
            "avg_fraud_score": round(avg_score, 4),
            "total_volume": round(total_volume, 2),
            "fraud_volume": round(fraud_volume, 2),
        }
