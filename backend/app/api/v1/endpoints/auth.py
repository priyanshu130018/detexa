"""
app/api/v1/endpoints/auth.py
─────────────────────────────────────────────────────────────────────────────
Authentication and user management REST API endpoints.
"""

import math
from typing import List
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Path, status
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_auth_service,
    get_current_admin_user,
    get_current_user,
)
from app.db.models import User
from app.models.schemas import (
    PaginatedResponse,
    TokenResponse,
    UserLogin,
    UserOut,
    UserRegister,
    UserStatusUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication & Users"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Create a new user profile and issue an initial Bearer JWT access token.",
)
def register(
    body: UserRegister,
    auth_svc: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth_svc.register(body)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticate via email and password to receive a Bearer JWT access token.",
)
def login(
    body: UserLogin,
    background_tasks: BackgroundTasks,
    auth_svc: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return auth_svc.login(body, background_tasks=background_tasks)


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current User Profile",
    description="Retrieve the profile of the currently authenticated user.",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


@router.get(
    "/users",
    response_model=PaginatedResponse[UserOut],
    summary="List Users (Admin Only)",
    description="Retrieve a paginated list of all registered platform users.",
)
def list_users(
    pagination: PaginationParams = Depends(),
    auth_svc: AuthService = Depends(get_auth_service),
    _: User = Depends(get_current_admin_user),
) -> PaginatedResponse[UserOut]:
    users = auth_svc.list_users(limit=pagination.limit, skip=pagination.skip)
    total = len(users)  # or count query
    pages = math.ceil(total / pagination.page_size) if total > 0 else 1
    return PaginatedResponse(
        items=users,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
        has_next=pagination.page < pages,
        has_prev=pagination.page > 1,
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=UserOut,
    summary="Update User Status (Admin Only)",
    description="Activate or deactivate a user account.",
)
def update_user_status(
    user_id: uuid.UUID = Path(..., description="Target User UUID"),
    body: UserStatusUpdate = ...,
    auth_svc: AuthService = Depends(get_auth_service),
    admin_user: User = Depends(get_current_admin_user),
) -> User:
    return auth_svc.update_user_status(user_id=user_id, is_active=body.is_active, admin_id=admin_user.id)
