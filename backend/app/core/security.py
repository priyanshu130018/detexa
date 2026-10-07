"""
app/core/security.py
─────────────────────────────────────────────────────────────────────────────
JWT creation / verification and password hashing helpers.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Password Utilities ───────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt (truncated to 72 bytes per bcrypt specification)."""
    if not plain:
        raise ValueError("Password cannot be empty")
    pwd_bytes = plain.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not plain or not hashed:
        return False
    try:
        pwd_bytes = plain.encode("utf-8")[:72]
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except (ValueError, TypeError, Exception):
        return False


# ── JWT Utilities ────────────────────────────────────────────────────────────

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Encode payload claims into a signed JWT token."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
