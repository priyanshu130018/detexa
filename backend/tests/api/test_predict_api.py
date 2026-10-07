"""
backend/tests/api/test_predict_api.py
─────────────────────────────────────────────────────────────────────────────
API endpoint tests for AI prediction services (/api/v1/predict).
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
class TestPredictAPI:
    def test_predict_credit_single_normal(self, client: TestClient, auth_headers: dict, sample_credit_transaction_payload):
        resp = client.post(
            "/api/v1/predict/credit",
            json=sample_credit_transaction_payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "fraud_score" in data
        assert "risk_level" in data
        assert "decision" in data
        assert 0.0 <= data["fraud_score"] <= 1.0
        assert data["decision"] in ("ALLOW", "CHALLENGE", "REVIEW", "BLOCK")

    def test_predict_credit_batch(self, client: TestClient, auth_headers: dict):
        batch = {
            "transactions": [
                {"amount": 40.0, "v1": 0.0, "v2": 0.0},
                {"amount": 8000.0, "v1": -4.0, "v2": 3.5},
            ]
        }
        resp = client.post(
            "/api/v1/predict/credit/batch",
            json=batch,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_processed"] == 2
        assert len(data["predictions"]) == 2

    def test_predict_behavior_anomaly(self, client: TestClient, auth_headers: dict, sample_behavior_payload):
        resp = client.post(
            "/api/v1/predict/behavior",
            json=sample_behavior_payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "anomaly_score" in data
        assert "is_anomalous" in data or "is_anomaly" in data
        assert "risk_factors" in data
        assert 0.0 <= data["anomaly_score"] <= 1.0

    def test_predict_credit_validation_error(self, client: TestClient, auth_headers: dict):
        # Negative amount
        resp = client.post(
            "/api/v1/predict/credit",
            json={"amount": -50.0},
            headers=auth_headers,
        )
        assert resp.status_code in [400, 422]
