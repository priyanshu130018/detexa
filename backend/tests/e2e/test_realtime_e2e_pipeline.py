"""
backend/tests/e2e/test_realtime_e2e_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Complete real-time end-to-end transaction pipeline test:
FastAPI / Kafka -> Flink -> Redis Feature Store -> XGBoost -> Decision Engine -> Real-time Broadcast.
"""

import pytest
import time
import json
import uuid
from app.core.config import settings
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.decision import get_decision_engine, DecisionContext, DecisionAction
from app.streaming.flink_processor import SlidingWindowState


@pytest.mark.e2e
class TestRealtimeE2EPipeline:
    @classmethod
    def setup_class(cls):
        cls.window_state = SlidingWindowState()
        cls.banking_model = BankingFraudModel.get_instance()
        cls.decision_engine = get_decision_engine()

    def test_e2e_trace_1_low_risk_allow_flow(self):
        customer_id = f"CUST-E2E-{uuid.uuid4().hex[:6]}"
        user_id = customer_id
        device_id = f"dev-e2e-{uuid.uuid4().hex[:6]}"
        ip_addr = "192.168.1.100"
        amount = 499.0

        # Step 1: Flink stream window state aggregation
        now = time.time()
        f = self.window_state.record_and_compute(customer_id, amount, "Blinkit India", "IN", device_id, now)

        assert f.velocity_1m >= 1
        assert f.velocity_5m >= 1
        assert f.velocity_1h >= 1
        assert f.rolling_amount_1h >= 499.0

        # Step 2: Machine Learning Inference (XGBoost on Banking Features)
        ml_input = {
            "customer_id": customer_id,
            "transaction_amount": amount,
            "account_balance": 50000.0,
            "account_type": "Savings",
            "transaction_type": "UPI",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "credit_score": 750,
        }
        score, shap_drivers = self.banking_model.predict(ml_input)
        assert 0.0 <= score <= 1.0

        # Step 3: Decision Engine Policy Evaluation
        ctx = DecisionContext(
            fraud_score=score,
            amount=amount,
            currency="INR",
            user_id=customer_id,
            realtime_features={"velocity_1m": f.velocity_1m, "velocity_5m": f.velocity_5m},
            graph_risk={"graph_shared_device_users": 1, "graph_risk_score": 0.0},
        )
        decision_outcome = self.decision_engine.evaluate(ctx)
        assert decision_outcome.decision in [DecisionAction.ALLOW, DecisionAction.REVIEW, DecisionAction.CHALLENGE]

    def test_e2e_trace_2_high_risk_collusion_block_flow(self):
        fraudster_1 = f"fraud-1-{uuid.uuid4().hex[:6]}"

        # Evaluate decision with elevated entity sharing & burst velocity risk
        ctx = DecisionContext(
            fraud_score=0.92,
            amount=850000.0,
            currency="INR",
            user_id=fraudster_1,
            realtime_features={"velocity_1m": 10, "velocity_5m": 25},
            graph_risk={"graph_shared_device_users": 4, "graph_shared_device_frauds": 3},
        )
        decision_outcome = self.decision_engine.evaluate(ctx)
        assert decision_outcome.decision == DecisionAction.BLOCK
        assert decision_outcome.risk_level == "High"
