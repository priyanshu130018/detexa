"""
app/api/v1/endpoints/transactions.py
─────────────────────────────────────────────────────────────────────────────
Financial Transactions REST API endpoints with SQL joins, filtering, and pagination.
"""

from datetime import datetime
import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_current_user, get_db, get_transaction_service
from app.db.models import User
from app.models.schemas import PaginatedResponse, TransactionDetailOut, TransactionOut
from app.repositories.transaction_repo import TransactionRepository
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get(
    "",
    response_model=PaginatedResponse[TransactionOut],
    summary="List & Filter Transactions",
    description="Retrieve paginated transactions with optional filters for fraud flag, risk level, amount, and text search.",
)
def list_transactions(
    pagination: PaginationParams = Depends(),
    is_fraud: Optional[bool] = Query(None, description="Filter by fraud classification boolean"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category (Low, Medium, High)"),
    search: Optional[str] = Query(None, description="Search term for merchant, reference, or user"),
    min_amount: Optional[float] = Query(None, ge=0, description="Minimum monetary transaction amount"),
    max_amount: Optional[float] = Query(None, ge=0, description="Maximum monetary transaction amount"),
    start_date: Optional[datetime] = Query(None, description="ISO timestamp lower bound"),
    end_date: Optional[datetime] = Query(None, description="ISO timestamp upper bound"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[TransactionOut]:
    repo = TransactionRepository(db)
    items, total = repo.list_filtered(
        skip=pagination.skip,
        limit=pagination.limit,
        is_fraud=is_fraud,
        risk_level=risk_level,
        search=search,
        min_amount=min_amount,
        max_amount=max_amount,
        start_date=start_date,
        end_date=end_date,
    )
    pages = math.ceil(total / pagination.page_size) if total > 0 else 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
        has_next=pagination.page < pages,
        has_prev=pagination.page > 1,
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailOut,
    summary="Get Transaction by ID",
    description="Retrieve full details for a transaction including Kaggle PCA components, device info, IP reputation, and merchant profile.",
)
def get_transaction(
    transaction_id: uuid.UUID = Path(..., description="Unique Transaction UUID"),
    txn_svc: TransactionService = Depends(get_transaction_service),
    _: User = Depends(get_current_user),
) -> TransactionDetailOut:
    return txn_svc.get_transaction_by_id(transaction_id)


@router.get(
    "/ref/{transaction_ref}",
    response_model=TransactionDetailOut,
    summary="Get Transaction by Reference Code",
    description="Retrieve transaction details using the unique business reference string (e.g. TXN-XXXX).",
)
def get_transaction_by_ref(
    transaction_ref: str = Path(..., description="Business transaction reference string"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> TransactionDetailOut:
    repo = TransactionRepository(db)
    txn = repo.get_by_ref(transaction_ref)
    if not txn:
        from app.core.exceptions import EntityNotFoundException
        raise EntityNotFoundException("Transaction", transaction_ref)
    return txn
