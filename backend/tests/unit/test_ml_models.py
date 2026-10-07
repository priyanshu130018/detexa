"""
backend/tests/unit/test_ml_models.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for Machine Learning models and inference wrappers.
"""

import pytest
from app.ml.models.credit_fraud_model import CreditFraudModel
from app.ml.models.behavior_model import BehaviorAnomalyModel


@pytest.mark.unit
class TestMLModelsUnit:
    def test_credit_fraud_model_singleton_and_loading(self):
        model1 = CreditFraudModel.get_instance()
        model2 = CreditFraudModel.get_instance()
        assert model1 is model2
        assert model1.MODEL_VERSION == "2.0.0"

    def test_credit_fraud_model_prediction_range(self):
        model = CreditFraudModel.get_instance()
        payload = {"amount": 100.0, "v1": 0.0, "v2": 0.0}
        score, shap_drivers = model.predict(payload)
        assert 0.0 <= score <= 1.0
        assert isinstance(score, float)
        if shap_drivers is not None:
            assert isinstance(shap_drivers, list)

    def test_credit_fraud_batch_prediction(self):
        model = CreditFraudModel.get_instance()
        payloads = [
            {"amount": 25.0, "v1": 0.1, "v2": -0.1},
            {"amount": 5000.0, "v1": -3.5, "v2": 4.0},
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
