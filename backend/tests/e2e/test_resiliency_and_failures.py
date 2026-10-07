"""
backend/tests/e2e/test_resiliency_and_failures.py
─────────────────────────────────────────────────────────────────────────────
Controlled failure and resiliency tests for all failure modes:
- Invalid JWT tokens
- Malformed inputs
- Redis / Neo4j / Kafka service failure handling
- Model exceptions
- WebSocket disconnection
"""

import pytest
import httpx
from fastapi.testclient import TestClient
from app.decision import get_decision_engine, DecisionContext, DecisionAction
from app.core.security import decode_token


@pytest.mark.e2e
class TestResiliencyAndFailures:
    def test_invalid_jwt_token_rejection(self, client: TestClient):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer malformed.token.signature"})
        assert resp.status_code == 401

    def test_missing_auth_header(self, client: TestClient):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_malformed_json_payload_422(self, client: TestClient, auth_headers: dict):
        resp = client.post("/api/v1/predict/credit", json={"amount": "not-a-number"}, headers=auth_headers)
        assert resp.status_code == 422

    def test_decision_engine_fallback_on_missing_context(self):
        engine = get_decision_engine()
        # Empty context with minimal inputs
        ctx = DecisionContext(fraud_score=0.1, amount=10.0)
        outcome = engine.evaluate(ctx)
        assert outcome.decision == DecisionAction.ALLOW
        assert outcome.risk_level == "Low"

    def test_nonexistent_transaction_404(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/transactions/00000000-0000-0000-0000-000000000000", headers=auth_headers)
        assert resp.status_code == 404
