"""
services/auth_service.py
─────────────────────────────────────────────────────────────────────────────
User registration, login, and token generation.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.security import hash_password, verify_password, create_access_token
from database.models import User
from models.schemas import UserRegister, UserLogin, TokenResponse


class AuthService:

    def __init__(self, db: Session):
        self.db = db

    def register(self, data: UserRegister) -> TokenResponse:
        existing = self.db.query(User).filter(User.email == data.email).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            id=uuid.uuid4(),
            name=data.name,
            email=data.email,
            mobile=data.mobile,
            hashed_password=hash_password(data.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return TokenResponse(
            access_token=token,
            user_id=str(user.id),
            name=user.name,
            email=user.email,
        )

    def login(self, data: UserLogin) -> TokenResponse:
        user: Optional[User] = self.db.query(User).filter(User.email == data.email).first()
        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        user.last_login = datetime.now(timezone.utc)
        self.db.commit()

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return TokenResponse(
            access_token=token,
            user_id=str(user.id),
            name=user.name,
            email=user.email,
        )
