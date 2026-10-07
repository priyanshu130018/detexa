"""
backend/tests/api/test_alerts_api.py
─────────────────────────────────────────────────────────────────────────────
API endpoint tests for fraud alerts management (/api/v1/alerts).
"""

import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.db.models import FraudAlert, AlertStatus, RiskLevel


@pytest.mark.api
class TestAlertsAPI:
    def test_list_alerts(self, client: TestClient, auth_headers: dict, db_session, test_user):
        alert = FraudAlert(
            id=uuid.uuid4(),
            user_id=test_user.id,
            alert_type="credit_fraud",
            risk_level=RiskLevel.HIGH.value,
            score=0.89,
            status=AlertStatus.OPEN.value,
            description="High risk alert for testing",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        db_session.commit()

        resp = client.get("/api/v1/alerts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data or isinstance(data, list)

    def test_get_alert_details(self, client: TestClient, auth_headers: dict, db_session, test_user):
        alert_id = uuid.uuid4()
        alert = FraudAlert(
            id=alert_id,
            user_id=test_user.id,
            alert_type="credit_fraud",
            risk_level=RiskLevel.HIGH.value,
            score=0.97,
            status=AlertStatus.OPEN.value,
            description="Critical risk alert",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        db_session.commit()

        resp = client.get(f"/api/v1/alerts/{alert_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(alert_id)
        assert data["risk_level"] == "High"

    def test_update_alert_status(self, client: TestClient, auth_headers: dict, db_session, test_user):
        alert_id = uuid.uuid4()
        alert = FraudAlert(
            id=alert_id,
            user_id=test_user.id,
            alert_type="behavior_anomaly",
            risk_level=RiskLevel.HIGH.value,
            score=0.79,
            status=AlertStatus.OPEN.value,
            description="To be updated",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        db_session.commit()

        patch_resp = client.patch(
            f"/api/v1/alerts/{alert_id}/status",
            json={"status": "resolved"},
            headers=auth_headers,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["status"] == "resolved"
