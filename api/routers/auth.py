"""
api/routers/auth.py
─────────────────────────────────────────────────────────────────────────────
POST /auth/register  – create a new account
POST /auth/login     – email + password → JWT
GET  /auth/me        – return current user profile
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.middleware.auth_middleware import get_current_user
from database.db import get_db
from database.models import User
from models.schemas import TokenResponse, UserLogin, UserOut, UserRegister
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    return AuthService(db).register(data)


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    return AuthService(db).login(data)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
