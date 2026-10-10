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


from app.core.redis import cache_get, cache_set

# ── Auth & Current User Dependencies ─────────────────────────────────────────

def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate Bearer JWT and return the authenticated User model (cached in Redis with 60s TTL)."""
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

    # 1. Fast-Path: Check Redis user cache
    cache_key = f"auth:user:{user_id_str}"
    cached_user_data = cache_get(cache_key)
    if cached_user_data and isinstance(cached_user_data, dict):
        if not cached_user_data.get("is_active", True):
            raise AuthorizationError("User account has been deactivated")
        created_val = cached_user_data.get("created_at")
        if isinstance(created_val, str):
            try:
                from datetime import datetime, timezone
                created_dt = datetime.fromisoformat(created_val)
            except Exception:
                from datetime import datetime, timezone
                created_dt = datetime.now(timezone.utc)
        elif isinstance(created_val, datetime):
            created_dt = created_val
        else:
            from datetime import datetime, timezone
            created_dt = datetime.now(timezone.utc)

        return User(
            id=uuid.UUID(cached_user_data["id"]),
            name=cached_user_data.get("name", "Detexa User"),
            email=cached_user_data.get("email", ""),
            mobile=cached_user_data.get("mobile"),
            is_active=bool(cached_user_data.get("is_active", True)),
            is_admin=bool(cached_user_data.get("is_admin", False)),
            created_at=created_dt,
        )

    # 2. Slow-Path: Query PostgreSQL on cache miss
    user_repo = UserRepository(db)
    user = user_repo.get(user_uuid)
    if not user:
        raise EntityNotFoundException("User", user_id_str)

    if not user.is_active:
        raise AuthorizationError("User account has been deactivated")

    # Populate Redis cache with 300-second TTL
    cache_set(
        cache_key,
        {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        ttl_seconds=300,
    )

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
