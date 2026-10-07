"""
backend/tests/api/test_auth_api.py
─────────────────────────────────────────────────────────────────────────────
API endpoint tests for authentication (/api/v1/auth).
"""

import pytest
import uuid
from fastapi.testclient import TestClient


@pytest.mark.api
class TestAuthAPI:
    def test_register_new_user(self, client: TestClient):
        email = f"api_user_{uuid.uuid4().hex[:6]}@detexa.io"
        resp = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "StrongPassword@2026",
            "name": "API Tester",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == email

    def test_register_duplicate_email_conflict(self, client: TestClient):
        email = f"dup_{uuid.uuid4().hex[:6]}@detexa.io"
        client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "StrongPassword@2026",
            "name": "API Tester",
        })
        # Attempt duplicate
        dup_resp = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "StrongPassword@2026",
            "name": "API Tester",
        })
        assert dup_resp.status_code in [400, 409]

    def test_login_success(self, client: TestClient):
        email = f"login_{uuid.uuid4().hex[:6]}@detexa.io"
        password = "ValidPassword@123"
        client.post("/api/v1/auth/register", json={
            "email": email,
            "password": password,
            "name": "Login User",
        })

        resp = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password,
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_invalid_credentials(self, client: TestClient):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nonexistent@detexa.io",
            "password": "WrongPassword123",
        })
        assert resp.status_code == 401

    def test_get_current_user_me(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data

    def test_get_current_user_unauthorized(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401
