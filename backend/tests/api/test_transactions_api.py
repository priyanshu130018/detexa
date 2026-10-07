"""
backend/tests/api/test_transactions_api.py
─────────────────────────────────────────────────────────────────────────────
API endpoint tests for transactions (/api/v1/transactions).
"""

import pytest
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.db.models import Transaction, RiskLevel


@pytest.mark.api
class TestTransactionsAPI:
    def test_list_transactions_empty(self, client: TestClient, auth_headers: dict):
        resp = client.get("/api/v1/transactions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_transactions_with_filters(self, client: TestClient, auth_headers: dict, db_session, test_user):
        # Insert sample transaction
        txn = Transaction(
            id=uuid.uuid4(),
            transaction_ref=f"TXN-FILTER-{uuid.uuid4().hex[:6]}",
            user_id=test_user.id,
            amount=420.0,
            currency="USD",
            merchant="Filter Merchant",
            category="electronics",
            country="US",
            risk_level=RiskLevel.HIGH,
            fraud_score=0.92,
            is_fraud=True,
            timestamp=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        db_session.commit()

        resp = client.get("/api/v1/transactions?risk_level=High&is_fraud=true", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(item["merchant"] == "Filter Merchant" for item in data["items"])

    def test_get_transaction_by_id(self, client: TestClient, auth_headers: dict, db_session, test_user):
        tx_id = uuid.uuid4()
        txn = Transaction(
            id=tx_id,
            transaction_ref=f"TXN-GET-{uuid.uuid4().hex[:6]}",
            user_id=test_user.id,
            amount=99.0,
            currency="USD",
            merchant="Get Merchant",
            category="Retail",
            country="US",
            risk_level=RiskLevel.LOW,
            fraud_score=0.04,
            is_fraud=False,
            timestamp=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        db_session.commit()

        resp = client.get(f"/api/v1/transactions/{tx_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(tx_id)
        assert data["merchant"] == "Get Merchant"

    def test_get_transaction_not_found(self, client: TestClient, auth_headers: dict):
        fake_id = uuid.uuid4()
        resp = client.get(f"/api/v1/transactions/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404
