"""
scripts/ensure_demo_user.py
─────────────────────────────────────────────────────────────────────────────
Safely ensures the canonical demo admin account (priyanshu@gmail.com)
is provisioned with admin privileges and secure password hash in PostgreSQL.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import logger
from app.core.security import hash_password, verify_password
from app.db.models import AuditLog, User
from app.db.session import SessionLocal

def ensure_demo_user(email: str = "priyanshu@gmail.com", name: str = "Priyanshu", password: str = "Admin@1234") -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        now_dt = datetime.now(timezone.utc)
        if user:
            print(f"User {email} already exists (ID: {user.id}, Active: {user.is_active}, Admin: {user.is_admin}).")
            # Verify password or update if needed
            if not verify_password(password, user.hashed_password):
                print(f"Updating password hash for existing user {email}...")
                user.hashed_password = hash_password(password)
                user.is_active = True
                user.is_admin = True
                db.commit()
                print("Password hash updated successfully.")
            return user
        
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            name=name,
            email=email.lower(),
            mobile="+91-9876543211",
            hashed_password=hash_password(password),
            is_admin=True,
            is_active=True,
            created_at=now_dt,
        )
        db.add(user)
        
        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=user_id,
            action="DEMO_USER_PROVISIONED",
            entity_type="user",
            entity_id=str(user_id),
            details={"email": email.lower(), "is_admin": True, "source": "ensure_demo_user"},
            created_at=now_dt,
        )
        db.add(audit)
        db.commit()
        print(f"Provisioned demo user {email} with Admin role (ID: {user_id}).")
        return user
    finally:
        db.close()

if __name__ == "__main__":
    ensure_demo_user()
