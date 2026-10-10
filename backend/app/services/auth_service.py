"""
app/services/auth_service.py
─────────────────────────────────────────────────────────────────────────────
Authentication and user management business logic with audit logging and atomic transactions.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.security import hash_password, verify_password, create_access_token
from app.db.models import AuditLog, User
from app.models.schemas import UserRegister, UserLogin, TokenResponse


from app.core.redis import cache_set

class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register(self, data: UserRegister, is_admin: bool = False) -> TokenResponse:
        existing = self.db.query(User).filter(User.email == data.email.lower()).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already registered",
            )

        user_id = uuid.uuid4()
        now_dt = datetime.now(timezone.utc)
        try:
            user = User(
                id=user_id,
                name=data.name,
                email=data.email.lower(),
                mobile=data.mobile,
                hashed_password=hash_password(data.password),
                is_active=True,
                is_admin=is_admin,
                created_at=now_dt,
            )
            self.db.add(user)

            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="USER_REGISTERED",
                entity_type="user",
                entity_id=str(user_id),
                details={"email": data.email.lower(), "is_admin": is_admin},
                created_at=now_dt,
            )
            self.db.add(audit)

            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to register user {data.email}: {exc}")
            raise HTTPException(status_code=500, detail="Database transaction failed during registration")

        # Cache in Redis immediately
        cache_set(
            f"auth:user:{user_id}",
            {
                "id": str(user_id),
                "name": data.name,
                "email": data.email.lower(),
                "mobile": data.mobile,
                "is_active": True,
                "is_admin": is_admin,
                "created_at": now_dt.isoformat(),
            },
            ttl_seconds=300,
        )

        token = create_access_token({"sub": str(user_id), "email": data.email.lower(), "is_admin": is_admin})
        return TokenResponse(
            access_token=token,
            user_id=str(user_id),
            name=data.name,
            email=data.email.lower(),
            is_admin=is_admin,
        )

    def record_login_audit(self, user_id: uuid.UUID, email: str):
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                u.last_login = datetime.now(timezone.utc)
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=user_id,
                action="USER_LOGGED_IN",
                entity_type="user",
                entity_id=str(user_id),
                details={"email": email},
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Could not record login timestamp/audit: {exc}")
        finally:
            db.close()

    def login(self, data: UserLogin, background_tasks: Optional[Any] = None) -> TokenResponse:
        try:
            user: Optional[User] = self.db.query(User).filter(User.email == data.email.lower()).first()
        except Exception as db_exc:
            logger.error(f"Database lookup failed during login for {data.email}: {db_exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection error. Unable to verify credentials at this time.",
            )

        if not user or not verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated. Contact an administrator.",
            )

        u_id = str(user.id)
        u_name = user.name
        u_email = user.email
        u_mobile = user.mobile
        u_admin = bool(user.is_admin)
        u_active = bool(user.is_active)
        u_created = user.created_at.isoformat() if user.created_at else datetime.now(timezone.utc).isoformat()

        # Cache authenticated user in Redis immediately to accelerate all subsequent requests
        cache_set(
            f"auth:user:{u_id}",
            {
                "id": u_id,
                "name": u_name,
                "email": u_email,
                "mobile": u_mobile,
                "is_active": u_active,
                "is_admin": u_admin,
                "created_at": u_created,
            },
            ttl_seconds=300,
        )

        if background_tasks is not None:
            background_tasks.add_task(self.record_login_audit, user.id, u_email)
        else:
            try:
                user.last_login = datetime.now(timezone.utc)
                audit = AuditLog(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    action="USER_LOGGED_IN",
                    entity_type="user",
                    entity_id=u_id,
                    details={"email": u_email},
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(audit)
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                logger.warning(f"Could not record login timestamp/audit: {exc}")

        token = create_access_token({"sub": u_id, "email": u_email, "is_admin": u_admin})
        return TokenResponse(
            access_token=token,
            user_id=u_id,
            name=u_name,
            email=u_email,
            is_admin=u_admin,
        )

    def list_users(self, limit: int = 50, skip: int = 0) -> List[User]:
        return self.db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    def update_user_status(self, user_id: uuid.UUID, is_active: bool, admin_id: Optional[uuid.UUID] = None) -> User:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            user.is_active = is_active
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=admin_id or user_id,
                action="USER_STATUS_UPDATED",
                entity_type="user",
                entity_id=str(user_id),
                details={"is_active": is_active},
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(audit)
            self.db.commit()
            self.db.refresh(user)
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Failed to update user status {user_id}: {exc}")
            raise HTTPException(status_code=500, detail="Database failure during user status update")

        return user
