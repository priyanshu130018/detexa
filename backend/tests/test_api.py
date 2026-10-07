"""
backend/tests/test_api.py
─────────────────────────────────────────────────────────────────────────────
FastAPI integration tests for Detexa backend API.
"""

import os
import pytest
from fastapi.testclient import TestClient

# Set testing environment variables before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-minimum!!"
os.environ["REDIS_ENABLED"] = "False"

from app.main import app
from app.db.base import Base
from app.db.session import engine

Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(scope="module")
def auth_token():
    email = "tester_api@detexa.io"
    password = "TestPass@1234"
    reg_resp = client.post("/api/v1/auth/register", json={
        "name": "Integration Tester",
        "email": email,
        "password": password,
    })
    if reg_resp.status_code == 201:
        return reg_resp.json()["access_token"]

    login_resp = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password,
    })
    return login_resp.json()["access_token"]


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


def test_readiness():
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_auth_flow(auth_token):
    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "tester_api@detexa.io"


def test_banking_prediction(auth_token):
    payload = {
        "customer_id": "CUST_9999",
        "account_type": "Savings",
        "transaction_type": "UPI",
        "transaction_amount": 2500.0,
        "account_balance": 35000.0,
        "merchant_category": "Electronics",
        "state": "Maharashtra",
        "credit_score": 740,
        "channel": "Mobile Banking",
        "kyc_status": "Verified",
    }

    resp = client.post(
        "/api/v1/predict/transaction",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "fraud_score" in data
    assert 0.0 <= data["fraud_score"] <= 1.0
    assert data["risk_level"] in ("Low", "Medium", "High")
    assert "explanation" in data
    assert "summary" in data["explanation"]
    assert "risk_factors" in data["explanation"]


def test_batch_banking_prediction(auth_token):
    batch = {
        "transactions": [
            {
                "customer_id": "CUST_1",
                "transaction_amount": 1000.0,
                "account_balance": 20000.0,
                "transaction_type": "UPI",
            },
            {
                "customer_id": "CUST_2",
                "transaction_amount": 50000.0,
                "account_balance": 1000.0,
                "transaction_type": "IMPS",
            },
        ]
    }
    resp = client.post(
        "/api/v1/predict/transaction/batch",
        json=batch,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_processed"] == 2
    assert len(data["predictions"]) == 2


def test_behavior_prediction(auth_token):
    payload = {
        "session_id": "test-session-123",
        "login_hour": 2,
        "typing_speed": 3.5,
        "mouse_velocity": 120.0,
        "is_vpn": True,
        "is_tor": False,
        "failed_logins": 2,
    }
    resp = client.post(
        "/api/v1/predict/behavior",
        json=payload,
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "anomaly_score" in data
    assert 0.0 <= data["anomaly_score"] <= 1.0


def test_alerts_and_stats(auth_token):
    stats_resp = client.get(
        "/api/v1/alerts/stats",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert stats_resp.status_code == 200
    assert "total_transactions" in stats_resp.json()

    alerts_resp = client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert alerts_resp.status_code == 200
    data = alerts_resp.json()
    assert "items" in data
    assert "total" in data


def test_transactions_listing(auth_token):
    resp = client.get(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
