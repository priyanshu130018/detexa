"""
backend/tests/unit/test_ml_models.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Machine Learning models and inference wrappers.
"""

import pytest
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.ml.models.behavior_model import BehaviorAnomalyModel


@pytest.mark.unit
class TestMLModelsUnit:
    def test_banking_fraud_model_singleton_and_loading(self):
        model1 = BankingFraudModel.get_instance()
        model2 = BankingFraudModel.get_instance()
        assert model1 is model2
        assert model1.MODEL_VERSION == "2.0.0"

    def test_banking_fraud_model_prediction_range(self):
        model = BankingFraudModel.get_instance()
        payload = {
            "customer_id": "CUST_1001",
            "account_type": "Savings",
            "transaction_type": "UPI",
            "transaction_amount": 1500.0,
            "transaction_direction": "Debit",
            "account_balance": 25000.0,
            "merchant_category": "Electronics",
            "state": "Maharashtra",
            "credit_score": 720,
            "has_loan": False,
            "loan_type": "None",
            "emi_amount": 0.0,
            "transaction_status": "Completed",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "transaction_hour": 14,
            "transaction_date": "2026-10-07",
            "transaction_time": "14:30:00",
        }
        score, shap_drivers = model.predict(payload)
        assert 0.0 <= score <= 1.0
        assert isinstance(score, float)
        if shap_drivers is not None:
            assert isinstance(shap_drivers, list)

    def test_banking_fraud_batch_prediction(self):
        model = BankingFraudModel.get_instance()
        payloads = [
            {
                "customer_id": "CUST_1001",
                "account_type": "Savings",
                "transaction_type": "UPI",
                "transaction_amount": 250.0,
                "account_balance": 15000.0,
                "merchant_category": "Grocery",
                "state": "Karnataka",
                "credit_score": 780,
                "channel": "Mobile Banking",
                "kyc_status": "Verified",
                "transaction_hour": 10,
            },
            {
                "customer_id": "CUST_9999",
                "account_type": "Current",
                "transaction_type": "IMPS",
                "transaction_amount": 450000.0,
                "account_balance": 1000.0,
                "merchant_category": "Jewellery",
                "state": "Maharashtra",
                "credit_score": 500,
                "channel": "Net Banking",
                "kyc_status": "Pending",
                "transaction_hour": 3,
            },
        ]
        results = model.predict_batch(payloads)
        assert len(results) == 2
        for score, shap in results:
            assert 0.0 <= score <= 1.0

    def test_behavior_anomaly_model_prediction(self):
        model = BehaviorAnomalyModel.get_instance()
        payload = {
            "session_id": "sess-unit-01",
            "login_hour": 2,
            "typing_speed": 1.2,
            "mouse_velocity": 500.0,
            "is_vpn": True,
            "is_tor": True,
            "failed_logins": 5,
        }
        score, latency, factors = model.predict(payload)
        assert 0.0 <= score <= 1.0
        assert latency >= 0.0
        assert isinstance(factors, list)
        assert "TOR Exit Node Connection" in factors
        assert "VPN / Proxy IP Detected" in factors
        assert "Multiple Failed Login Attempts (5)" in factors
