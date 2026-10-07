"""
app/api/deps.py
─────────────────────────────────────────────────────────────────────────────
FastAPI dependencies for authentication, authorization, pagination, and services.
"""

from typing import Generator, Optional
import uuid

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError, AuthorizationError, EntityNotFoundException
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db
from app.repositories.user_repo import UserRepository
from app.services.alert_service import AlertService
from app.services.auth_service import AuthService
from app.services.behavior_service import BehaviorDetectionService
from app.services.dashboard_service import DashboardService
from app.services.decision_service import DecisionService
from app.services.fraud_service import FraudDetectionService
from app.services.transaction_service import TransactionService

security_scheme = HTTPBearer(auto_error=False)


# ── Pagination Dependency ───────────────────────────────────────────────────

class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (1-indexed)"),
        page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size


# ── Auth & Current User Dependencies ─────────────────────────────────────────

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return the authenticated User model."""
    if not auth_header:
        raise AuthenticationError("Authorization header missing")

    token = auth_header.credentials
    payload = decode_token(token)
    if not payload:
        raise AuthenticationError("Invalid or expired authentication token")

    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise AuthenticationError("Token payload missing user identifier")

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise AuthenticationError("Invalid user ID in token")

    user_repo = UserRepository(db)
    user = user_repo.get(user_uuid)
    if not user:
        raise EntityNotFoundException("User", user_id_str)

    if not user.is_active:
        raise AuthorizationError("User account has been deactivated")

    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Ensure current authenticated user holds Administrator privileges."""
    if not current_user.is_admin:
        raise AuthorizationError("Administrator privileges required for this operation")
    return current_user


# ── Service Factory Dependencies ─────────────────────────────────────────────

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_fraud_service(db: Session = Depends(get_db)) -> FraudDetectionService:
    return FraudDetectionService(db)


def get_behavior_service(db: Session = Depends(get_db)) -> BehaviorDetectionService:
    return BehaviorDetectionService(db)


def get_transaction_service(db: Session = Depends(get_db)) -> TransactionService:
    return TransactionService(db)


def get_alert_service(db: Session = Depends(get_db)) -> AlertService:
    return AlertService(db)


def get_decision_service(db: Session = Depends(get_db)) -> DecisionService:
    return DecisionService(db)


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)
