"""
backend/tests/unit/test_decision_engine.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive Unit Tests for Detexa Decision Engine.
Validates:
- 5+ distinct cases each for ALLOW, CHALLENGE, REVIEW, and BLOCK
- Boundary threshold conditions around 0.40, 0.60, 0.65, 0.85
- Amount spikes, burst velocities, multi-device graph collusions, and auth decline streaks
"""

import pytest
from app.decision import (
    get_decision_engine,
    DecisionContext,
    DecisionAction,
    AmountSpikeRule,
    VelocityBurstRule,
    GraphCollusionRule,
    IPHoppingRule,
    MLScoreThresholdRule,
    AuthenticationFailureRule,
    DiurnalTimingRule,
)


@pytest.mark.unit
class TestDecisionEngineUnit:
    def setup_method(self):
        self.engine = get_decision_engine()

    # ── 1. ALLOW SCENARIOS (>=5 Distinct Cases) ──────────────────────────────
    
    def test_allow_case_1_clean_low_amount_upi(self):
        ctx = DecisionContext(
            fraud_score=0.04,
            amount=150.0,
            currency="INR",
            merchant="BigBasket",
            category="Grocery",
            realtime_features={"velocity_1m": 1, "velocity_5m": 1, "failed_auth_5m": 0},
            graph_risk={"graph_risk_score": 0.01, "graph_shared_device_users": 1},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.ALLOW
        assert res.risk_level == "Low"
        assert not res.requires_step_up_auth

    def test_allow_case_2_trusted_customer_normal_balance(self):
        ctx = DecisionContext(
            fraud_score=0.12,
            amount=1200.0,
            currency="INR",
            merchant="Amazon India",
            category="Retail",
            realtime_features={"velocity_1m": 1, "velocity_5m": 2, "amount_deviation_ratio": 1.1},
            graph_risk={"graph_risk_score": 0.05, "graph_shared_device_users": 1},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.ALLOW
        assert res.risk_level == "Low"

    def test_allow_case_3_utility_bill_payment(self):
        ctx = DecisionContext(
            fraud_score=0.18,
            amount=2500.0,
            currency="INR",
            merchant="Tata Power",
            category="Utilities",
            realtime_features={"velocity_1m": 1, "velocity_5m": 1},
            graph_risk={"graph_risk_score": 0.02},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.ALLOW
        assert res.risk_level == "Low"

    def test_allow_case_4_recurring_emi_debit(self):
        ctx = DecisionContext(
            fraud_score=0.25,
            amount=8500.0,
            currency="INR",
            merchant="HDFC Loan",
            category="Financial",
            realtime_features={"velocity_1m": 1, "velocity_5m": 1, "amount_deviation_ratio": 1.0},
            graph_risk={"graph_risk_score": 0.03},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.ALLOW
        assert res.risk_level == "Low"

    def test_allow_case_5_below_allow_threshold_boundary(self):
        # 0.38 is strictly < 0.40 allow boundary with clean signals
        ctx = DecisionContext(
            fraud_score=0.38,
            amount=450.0,
            currency="INR",
            merchant="Zomato",
            category="Food",
            realtime_features={"velocity_1m": 1, "velocity_5m": 1},
            graph_risk={"graph_risk_score": 0.05},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.ALLOW
        assert res.risk_level == "Low"

    # ── 2. CHALLENGE SCENARIOS (>=5 Distinct Cases) ──────────────────────────

    def test_challenge_case_1_moderate_ml_score(self):
        ctx = DecisionContext(
            fraud_score=0.45,
            amount=3500.0,
            currency="INR",
            merchant="Croma Electronics",
            category="Electronics",
            realtime_features={"velocity_1m": 2, "velocity_5m": 3},
            graph_risk={"graph_risk_score": 0.15},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.CHALLENGE
        assert res.risk_level == "Medium"
        assert res.requires_step_up_auth is True

    def test_challenge_case_2_repeat_declines_auth_streak(self):
        ctx = DecisionContext(
            fraud_score=0.20,
            amount=600.0,
            currency="INR",
            realtime_features={"failed_auth_5m": 2, "consecutive_failures": 2},
            graph_risk={"graph_risk_score": 0.10},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.CHALLENGE
        assert res.requires_step_up_auth is True

    def test_challenge_case_3_unusual_night_hours_high_value(self):
        ctx = DecisionContext(
            fraud_score=0.30,
            amount=850.0,
            currency="INR",
            realtime_features={"hour_of_day": 3.0, "is_unusual_hour": True},
            graph_risk={"graph_risk_score": 0.10},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.CHALLENGE
        assert res.requires_step_up_auth is True

    def test_challenge_case_4_ip_hopping_detected(self):
        ctx = DecisionContext(
            fraud_score=0.32,
            amount=1500.0,
            currency="INR",
            realtime_features={"ip_changed": True, "distinct_ips_15m": 2},
            graph_risk={"graph_risk_score": 0.12},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.CHALLENGE
        assert res.requires_step_up_auth is True

    def test_challenge_case_5_at_0_60_threshold_boundary(self):
        # 0.60 is between 0.40 and 0.65 (triggers ML moderate challenge)
        ctx = DecisionContext(
            fraud_score=0.60,
            amount=2000.0,
            currency="INR",
            realtime_features={"velocity_1m": 1, "velocity_5m": 2},
            graph_risk={"graph_risk_score": 0.20},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.CHALLENGE
        assert res.requires_step_up_auth is True

    # ── 3. REVIEW SCENARIOS (>=5 Distinct Cases) ─────────────────────────────

    def test_review_case_1_high_ml_score_tier(self):
        ctx = DecisionContext(
            fraud_score=0.72,
            amount=15000.0,
            currency="INR",
            merchant="Jewellery Outlet",
            category="Jewellery",
            realtime_features={"velocity_1m": 2, "velocity_5m": 4},
            graph_risk={"graph_risk_score": 0.35},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.REVIEW
        assert res.risk_level in ("Medium", "High")

    def test_review_case_2_hard_amount_spike_limit(self):
        ctx = DecisionContext(
            fraud_score=0.25,
            amount=15000.0,  # > rule_max_amount_hard_limit (10000.0)
            currency="INR",
            realtime_features={"velocity_1m": 1, "velocity_5m": 1},
            graph_risk={"graph_risk_score": 0.10},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.REVIEW

    def test_review_case_3_elevated_5m_velocity(self):
        ctx = DecisionContext(
            fraud_score=0.35,
            amount=800.0,
            currency="INR",
            realtime_features={"velocity_5m": 14},  # >= 12 threshold
            graph_risk={"graph_risk_score": 0.15},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.REVIEW

    def test_review_case_4_just_above_0_65_review_threshold(self):
        ctx = DecisionContext(
            fraud_score=0.66,
            amount=4500.0,
            currency="INR",
            realtime_features={"velocity_1m": 1, "velocity_5m": 2},
            graph_risk={"graph_risk_score": 0.20},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.REVIEW

    def test_review_case_5_below_0_85_boundary(self):
        # 0.849 is strictly below 0.85 block threshold, routes to manual REVIEW
        ctx = DecisionContext(
            fraud_score=0.849,
            amount=9500.0,
            currency="INR",
            realtime_features={"velocity_1m": 2, "velocity_5m": 4},
            graph_risk={"graph_risk_score": 0.45},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.REVIEW
        assert res.risk_level == "High"

    # ── 4. BLOCK SCENARIOS (>=5 Distinct Cases) ──────────────────────────────

    def test_block_case_1_critical_ml_score_at_or_above_0_85(self):
        ctx = DecisionContext(
            fraud_score=0.86,
            amount=5000.0,
            currency="INR",
            realtime_features={"velocity_1m": 1, "velocity_5m": 2},
            graph_risk={"graph_risk_score": 0.30},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.BLOCK
        assert res.risk_level == "High"

    def test_block_case_2_extreme_burst_velocity(self):
        ctx = DecisionContext(
            fraud_score=0.20,
            amount=200.0,
            currency="INR",
            realtime_features={"velocity_1m": 8},  # >= 5 limit
            graph_risk={"graph_risk_score": 0.10},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.BLOCK
        assert res.risk_level == "High"

    def test_block_case_3_graph_fraud_ring_shared_device(self):
        ctx = DecisionContext(
            fraud_score=0.35,
            amount=1200.0,
            currency="INR",
            graph_risk={"graph_shared_device_users": 6},  # >= 3 limit
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.BLOCK
        assert res.risk_level == "High"

    def test_block_case_4_excessive_auth_failures(self):
        ctx = DecisionContext(
            fraud_score=0.40,
            amount=3000.0,
            currency="INR",
            realtime_features={"failed_auth_5m": 5},  # >= 3 limit
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.BLOCK
        assert res.risk_level == "High"

    def test_block_case_5_critical_composite_anomaly(self):
        ctx = DecisionContext(
            fraud_score=0.98,
            amount=450000.0,
            currency="INR",
            realtime_features={"velocity_1m": 10, "is_tor": True},
            graph_risk={"graph_risk_score": 0.95, "graph_shared_device_users": 10},
        )
        res = self.engine.evaluate(ctx)
        assert res.decision == DecisionAction.BLOCK
        assert res.risk_level == "High"

    # ── 5. THRESHOLD BOUNDARY TESTS (Around 0.60 and 0.85) ───────────────────

    def test_threshold_boundary_around_0_60(self):
        rule = MLScoreThresholdRule()
        
        # 0.59 -> CHALLENGE (between 0.40 and 0.65)
        ctx_59 = DecisionContext(fraud_score=0.59, amount=100.0)
        res_59 = rule.evaluate(ctx_59)
        assert res_59.action == DecisionAction.CHALLENGE

        # 0.60 -> CHALLENGE
        ctx_60 = DecisionContext(fraud_score=0.60, amount=100.0)
        res_60 = rule.evaluate(ctx_60)
        assert res_60.action == DecisionAction.CHALLENGE

        # 0.65 -> REVIEW (>= 0.65)
        ctx_65 = DecisionContext(fraud_score=0.65, amount=100.0)
        res_65 = rule.evaluate(ctx_65)
        assert res_65.action == DecisionAction.REVIEW

    def test_threshold_boundary_around_0_85(self):
        rule = MLScoreThresholdRule()

        # 0.84 -> REVIEW (< 0.85)
        ctx_84 = DecisionContext(fraud_score=0.84, amount=100.0)
        res_84 = rule.evaluate(ctx_84)
        assert res_84.action == DecisionAction.REVIEW

        # 0.85 -> BLOCK (>= 0.85)
        ctx_85 = DecisionContext(fraud_score=0.85, amount=100.0)
        res_85 = rule.evaluate(ctx_85)
        assert res_85.action == DecisionAction.BLOCK

        # 0.86 -> BLOCK
        ctx_86 = DecisionContext(fraud_score=0.86, amount=100.0)
        res_86 = rule.evaluate(ctx_86)
        assert res_86.action == DecisionAction.BLOCK
