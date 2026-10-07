"""
backend/tests/unit/test_decision_engine.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the Fraud Decision Engine and business rule evaluations.
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
)


@pytest.mark.unit
class TestDecisionEngineUnit:
    def test_decision_engine_allow_scenario(self):
        engine = get_decision_engine()
        ctx = DecisionContext(
            fraud_score=0.05,
            amount=30.0,
            currency="USD",
            realtime_features={"tx_count_1h": 1, "velocity_1m": 1},
            graph_risk={"graph_risk_score": 0.02},
        )
        outcome = engine.evaluate(ctx)
        assert outcome.decision == DecisionAction.ALLOW
        assert outcome.risk_level == "Low"
        assert outcome.requires_step_up_auth is False

    def test_decision_engine_challenge_scenario(self):
        engine = get_decision_engine()
        ctx = DecisionContext(
            fraud_score=0.48,
            amount=350.0,
            currency="USD",
            realtime_features={"tx_count_1h": 3, "velocity_1m": 2},
            graph_risk={"graph_risk_score": 0.15},
        )
        outcome = engine.evaluate(ctx)
        assert outcome.decision in (DecisionAction.CHALLENGE, DecisionAction.REVIEW)
        assert outcome.risk_level in ("Medium", "High")

    def test_decision_engine_review_scenario(self):
        engine = get_decision_engine()
        ctx = DecisionContext(
            fraud_score=0.75,
            amount=1500.0,
            currency="USD",
            realtime_features={"tx_count_1h": 6, "velocity_1m": 3},
            graph_risk={"graph_risk_score": 0.60},
        )
        outcome = engine.evaluate(ctx)
        assert outcome.decision in (DecisionAction.REVIEW, DecisionAction.BLOCK)
        assert outcome.risk_level == "High"

    def test_decision_engine_block_scenario(self):
        engine = get_decision_engine()
        ctx = DecisionContext(
            fraud_score=0.96,
            amount=9999.0,
            currency="USD",
            realtime_features={"tx_count_1h": 20, "is_tor": True},
            graph_risk={"graph_risk_score": 0.95},
        )
        outcome = engine.evaluate(ctx)
        assert outcome.decision == DecisionAction.BLOCK
        assert outcome.risk_level == "High"

    def test_amount_spike_rule_trigger(self):
        rule = AmountSpikeRule()
        ctx_spike = DecisionContext(fraud_score=0.1, amount=15000.0)
        result = rule.evaluate(ctx_spike)
        assert result is not None
        assert result.triggered is True
        assert result.action in [DecisionAction.REVIEW, DecisionAction.BLOCK]

    def test_velocity_burst_rule_trigger(self):
        rule = VelocityBurstRule()
        ctx_burst = DecisionContext(fraud_score=0.1, amount=50.0, realtime_features={"velocity_1m": 12})
        result = rule.evaluate(ctx_burst)
        assert result is not None
        assert result.triggered is True
        assert result.action in [DecisionAction.BLOCK, DecisionAction.CHALLENGE, DecisionAction.REVIEW]

    def test_graph_collusion_rule_trigger(self):
        rule = GraphCollusionRule()
        ctx_collusion = DecisionContext(fraud_score=0.2, amount=100.0, graph_risk={"graph_shared_device_users": 6})
        result = rule.evaluate(ctx_collusion)
        assert result is not None
        assert result.triggered is True
        assert result.action in [DecisionAction.BLOCK, DecisionAction.CHALLENGE]

