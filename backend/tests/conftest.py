"""
backend/tests/conftest.py
─────────────────────────────────────────────────────────────────────────────
Shared pytest fixtures for Detexa unit, integration, api, and e2e test suites.
"""

import os
import sys
import uuid
import time
import pytest
from datetime import datetime, timezone
from typing import Generator, Dict, Any

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.models import User, AlertStatus, RiskLevel, DecisionType, Transaction, FraudAlert
from app.db.session import get_db
from app.core.security import create_access_token, hash_password

# Test SQLite in-memory engine for unit/mocked database tests
TEST_SQLITE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    TEST_SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create in-memory schema for fast unit testing."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator:
    """Yield an isolated testing database session with automatic rollback."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def test_user(db_session) -> User:
    """Create a persistent test user in the session."""
    user = User(
        id=uuid.uuid4(),
        email=f"tester_{uuid.uuid4().hex[:6]}@detexa.io",
        hashed_password=hash_password("SecurePassword@2026"),
        name="Detexa Automated Tester",
        is_active=True,
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Generate a valid signed JWT access token."""
    return create_access_token({
        "sub": str(test_user.id),
        "is_admin": test_user.is_admin,
        "email": test_user.email,
    })


@pytest.fixture
def auth_headers(auth_token: str) -> Dict[str, str]:
    """Return standard HTTP Bearer Authorization header."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """Create a FastAPI TestClient overriding get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_credit_transaction_payload() -> Dict[str, Any]:
    """Normal low-risk credit transaction payload."""
    payload = {
        "amount": 45.50,
        "currency": "USD",
        "merchant": "Whole Foods Market",
        "category": "groceries",
        "country": "US",
        "device_fingerprint": "dev-trusted-01",
        "ip_address": "12.34.56.78",
    }
    for i in range(1, 29):
        payload[f"v{i}"] = 0.01
    return payload


@pytest.fixture
def suspicious_credit_transaction_payload() -> Dict[str, Any]:
    """High-risk anomalous transaction payload."""
    payload = {
        "amount": 9500.00,
        "currency": "USD",
        "merchant": "Offshore Crypto Exchange",
        "category": "cryptocurrency",
        "country": "XX",
        "device_fingerprint": "dev-tor-01",
        "ip_address": "198.51.100.99",
        "v1": -4.5, "v2": 3.8, "v3": -5.2, "v4": 4.9, "v14": -7.5, "v17": -8.1
    }
    for i in range(1, 29):
        if f"v{i}" not in payload:
            payload[f"v{i}"] = -1.2 if i % 2 == 0 else 1.5
    return payload


@pytest.fixture
def sample_behavior_payload() -> Dict[str, Any]:
    """Sample user behavior session telemetry."""
    return {
        "session_id": "sess-test-12345",
        "login_hour": 14,
        "typing_speed": 4.2,
        "mouse_velocity": 180.0,
        "is_vpn": False,
        "is_tor": False,
        "failed_logins": 0,
    }
