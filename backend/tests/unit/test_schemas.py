"""
backend/tests/unit/test_schemas.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Pydantic request/response schemas, field validations, and limits.
"""

import pytest
from pydantic import ValidationError
from app.models.schemas import (
    TransactionIn,
    BatchBankingFraudIn,
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
            "customer_id": "CUST_1001",
            "account_type": "Savings",
            "transaction_type": "UPI",
            "transaction_amount": 1200.50,
            "transaction_direction": "Debit",
            "account_balance": 45000.0,
            "merchant_category": "Electronics",
            "state": "Maharashtra",
            "credit_score": 750,
            "has_loan": False,
            "loan_type": "None",
            "emi_amount": 0.0,
            "transaction_status": "Completed",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "transaction_hour": 14,
            "currency": "INR",
        }
        tx = TransactionIn(**data)
        assert tx.transaction_amount == 1200.50
        assert tx.currency == "INR"
        assert tx.customer_id == "CUST_1001"
        assert tx.transaction_type == "UPI"

    def test_invalid_transaction_negative_amount(self):
        with pytest.raises(ValidationError):
            TransactionIn(transaction_amount=-50.0)

    def test_valid_batch_banking_fraud(self):
        batch_data = {
            "transactions": [
                {"customer_id": "CUST_1", "transaction_amount": 500.0, "account_balance": 5000.0},
                {"customer_id": "CUST_2", "transaction_amount": 10000.0, "account_balance": 20000.0},
            ]
        }
        batch = BatchBankingFraudIn(**batch_data)
        assert len(batch.transactions) == 2
        assert batch.transactions[0].transaction_amount == 500.0

    def test_empty_batch_rejection(self):
        with pytest.raises(ValidationError):
            BatchBankingFraudIn(transactions=[])

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
        res = AlertResolutionRequest(resolution_notes="Verified with customer successfully.", status="resolved")
        assert res.status == "resolved"
        assert "Verified" in res.resolution_notes
