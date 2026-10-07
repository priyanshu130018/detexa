"""
backend/tests/api/test_dashboard_and_health_api.py
─────────────────────────────────────────────────────────────────────────────
API endpoint tests for dashboard telemetry and health/readiness endpoints.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
class TestDashboardAndHealthAPI:
    def test_healthcheck_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["app"] == "Detexa"
        assert data["version"] == "2.0.0"

    def test_readiness_probe_endpoint(self, client: TestClient):
        resp = client.get("/health/ready")
        assert resp.status_code in (200, 503)
        assert "status" in resp.json()

    def test_dashboard_summary(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_transactions" in data
        assert "fraud_count" in data
        assert "fraud_rate" in data

    def test_dashboard_trend(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/dashboard/trends?days=7", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_streaming_metrics(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/streaming/metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "kafka_enabled" in data
        assert "transactions_topic" in data
