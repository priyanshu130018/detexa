"""
tests/test_api.py
─────────────────────────────────────────────────────────────────────────────
Basic API smoke tests using FastAPI's TestClient.

Run:  pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

# Patch DB to use SQLite in-memory for tests
import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-32-chars-minimum!!"

from api.main import app
from database.db import engine
from database.models import Base

Base.metadata.create_all(bind=engine)

client = TestClient(app)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    # Register
    resp = client.post("/api/v1/auth/register", json={
        "name": "Test User",
        "email": "testuser@detexa.io",
        "password": "TestPass@1234",
    })
    assert resp.status_code == 201
    return resp.json()["access_token"]


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_register_duplicate(auth_token):
    resp = client.post("/api/v1/auth/register", json={
        "name": "Dup",
        "email": "testuser@detexa.io",
        "password": "TestPass@1234",
    })
    assert resp.status_code == 400


def test_login_success():
    resp = client.post("/api/v1/auth/login", json={
        "email": "testuser@detexa.io",
        "password": "TestPass@1234",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_login_wrong_password():
    resp = client.post("/api/v1/auth/login", json={
        "email": "testuser@detexa.io",
        "password": "WrongPassword",
    })
    assert resp.status_code == 401


def test_me(auth_token):
    resp = client.get("/api/v1/auth/me",
                      headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "testuser@detexa.io"


# ── Prediction tests ──────────────────────────────────────────────────────────

def test_predict_credit(auth_token):
    payload = {"amount": 150.0}
    for i in range(1, 29):
        payload[f"v{i}"] = 0.0
    resp = client.post("/api/v1/predict/credit",
                       json=payload,
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "fraud_score" in data
    assert 0.0 <= data["fraud_score"] <= 1.0
    assert data["risk_level"] in ("Low", "Medium", "High")


def test_predict_behavior(auth_token):
    payload = {
        "session_id": "abc123",
        "login_hour": 3,
        "typing_speed": 1.0,
        "mouse_velocity": 50.0,
        "is_vpn": True,
        "is_tor": False,
        "failed_logins": 4,
        "device_change": True,
    }
    resp = client.post("/api/v1/predict/behavior",
                       json=payload,
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "anomaly_score" in data
    assert 0.0 <= data["anomaly_score"] <= 1.0


# ── Alerts tests ──────────────────────────────────────────────────────────────

def test_get_stats(auth_token):
    resp = client.get("/api/v1/alerts/stats",
                      headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    stats = resp.json()
    assert "total_transactions" in stats


def test_get_alerts(auth_token):
    resp = client.get("/api/v1/alerts",
                      headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
