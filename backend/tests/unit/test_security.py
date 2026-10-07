"""
backend/tests/unit/test_security.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for password hashing, bcrypt verification, and JWT lifecycle.
"""

import pytest
import time
from datetime import timedelta
from app.core.security import hash_password, verify_password, create_access_token, decode_token


@pytest.mark.unit
class TestSecurityUnit:
    def test_password_hashing_success(self):
        raw = "MySecretPass@123"
        hashed = hash_password(raw)
        assert hashed != raw
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
        assert verify_password(raw, hashed) is True

    def test_password_verification_failure(self):
        raw = "MySecretPass@123"
        hashed = hash_password(raw)
        assert verify_password("WrongPassword@999", hashed) is False
        assert verify_password("", hashed) is False
        assert verify_password(raw, "") is False

    def test_password_truncation_safety_72_bytes(self):
        # Bcrypt standard max length is 72 bytes. Verify strings exceeding 72 chars hash properly
        long_pass = "A" * 150
        hashed = hash_password(long_pass)
        assert verify_password(long_pass, hashed) is True
        # Prefix match under 72 chars
        assert verify_password("A" * 72, hashed) is True
        assert verify_password("B" * 150, hashed) is False

    def test_empty_password_exception(self):
        with pytest.raises(ValueError):
            hash_password("")

    def test_jwt_token_creation_and_decoding(self):
        data = {"sub": "user-uuid-1234", "role": "admin", "custom_claim": "test_val"}
        token = create_access_token(data, expires_delta=timedelta(minutes=15))
        assert isinstance(token, str)

        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "user-uuid-1234"
        assert decoded["role"] == "admin"
        assert decoded["custom_claim"] == "test_val"
        assert "exp" in decoded

    def test_jwt_expired_token(self):
        data = {"sub": "user-uuid-1234"}
        # Expired token 1 second in the past
        token = create_access_token(data, expires_delta=timedelta(seconds=-5))
        decoded = decode_token(token)
        assert decoded is None

    def test_jwt_invalid_token_string(self):
        assert decode_token("invalid.token.structure") is None
        assert decode_token("") is None
