"""
backend/tests/unit/test_schemas.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Pydantic request/response schemas, field validations, and limits.
"""

import pytest
from pydantic import ValidationError
from app.models.schemas import (
    TransactionIn,
    BatchCreditFraudIn,
    BehaviorIn,
    UserRegister,
    UserLogin,
    AlertStatusUpdate,
    AlertResolutionRequest,
)


@pytest.mark.unit
class TestSchemasUnit:
    def test_valid_transaction_in(self):
        data = {
            "amount": 120.50,
            "currency": "USD",
            "merchant": "Amazon Services",
            "category": "Retail",
            "v1": -0.5,
            "v28": 0.12,
        }
        tx = TransactionIn(**data)
        assert tx.amount == 120.50
        assert tx.currency == "USD"
        assert tx.merchant == "Amazon Services"
        assert tx.v1 == -0.5

    def test_invalid_transaction_negative_amount(self):
        with pytest.raises(ValidationError):
            TransactionIn(amount=-50.0)

    def test_valid_batch_credit_fraud(self):
        batch_data = {
            "transactions": [
                {"amount": 50.0, "v1": 0.1},
                {"amount": 1000.0, "v1": -2.5, "v2": 3.0},
            ]
        }
        batch = BatchCreditFraudIn(**batch_data)
        assert len(batch.transactions) == 2
        assert batch.transactions[0].amount == 50.0

    def test_empty_batch_rejection(self):
        with pytest.raises(ValidationError):
            BatchCreditFraudIn(transactions=[])

    def test_valid_behavior_in(self):
        data = {
            "session_id": "sess-999",
            "login_hour": 15,
            "typing_speed": 4.5,
            "mouse_velocity": 220.0,
            "is_vpn": True,
            "is_tor": False,
            "failed_logins": 1,
        }
        b = BehaviorIn(**data)
        assert b.session_id == "sess-999"
        assert b.login_hour == 15
        assert b.is_vpn is True

    def test_invalid_behavior_login_hour(self):
        with pytest.raises(ValidationError):
            BehaviorIn(session_id="s1", login_hour=25)  # Out of 0-23 range

    def test_user_register_validation(self):
        valid = UserRegister(email="test@detexa.io", password="SecurePassword123", name="Test Analyst")
        assert valid.email == "test@detexa.io"
        assert valid.name == "Test Analyst"

        # Invalid email
        with pytest.raises(ValidationError):
            UserRegister(email="not-an-email", password="ValidPassword123", name="Test")

        # Too short password
        with pytest.raises(ValidationError):
            UserRegister(email="test@detexa.io", password="short", name="Test")

    def test_alert_status_update(self):
        update = AlertStatusUpdate(status="resolved")
        assert update.status == "resolved"

    def test_alert_resolution_request(self):
        res = AlertResolutionRequest(resolution_notes="Verified with cardholder successfully.", status="resolved")
        assert res.status == "resolved"
        assert "Verified" in res.resolution_notes
