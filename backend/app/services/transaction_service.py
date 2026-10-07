"""
app/services/transaction_service.py
─────────────────────────────────────────────────────────────────────────────
Transaction querying, search, and detail retrieval using optimized SQL joins.
"""

from typing import List, Optional
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.db.models import Transaction, Merchant, User


class TransactionService:
    def __init__(self, db: Session):
        self.db = db

    def list_transactions(
        self,
        limit: int = 100,
        skip: int = 0,
        is_fraud: Optional[bool] = None,
        risk_level: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Transaction]:
        """Query transactions using SQL joins across Merchant and User relations."""
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

        if search:
            search_pattern = f"%{search}%"
            # Join Merchant and User for relational text search
            q = (
                q.outerjoin(Transaction.merchant_rel)
                .outerjoin(Transaction.user)
                .filter(
                    (Transaction.merchant.ilike(search_pattern))
                    | (Merchant.name.ilike(search_pattern))
                    | (Transaction.transaction_ref.ilike(search_pattern))
                    | (Transaction.category.ilike(search_pattern))
                    | (User.name.ilike(search_pattern))
                    | (User.email.ilike(search_pattern))
                )
            )

        return (
            q.order_by(Transaction.timestamp.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_transaction_by_id(self, txn_id: uuid.UUID) -> Transaction:
        """Retrieve single transaction with fully eager-loaded normalized relations."""
        txn = (
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
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")
        return txn
