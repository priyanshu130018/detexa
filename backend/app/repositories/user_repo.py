"""
app/repositories/user_repo.py
─────────────────────────────────────────────────────────────────────────────
User entity repository for authentication and profile management.
"""

from typing import List, Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models import User
from app.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email.strip().lower()).first()

    def list_users(self, skip: int = 0, limit: int = 50) -> List[User]:
        return self.db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
