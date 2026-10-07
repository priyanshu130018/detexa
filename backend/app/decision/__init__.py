"""
app/decision/__init__.py
─────────────────────────────────────────────────────────────────────────────
Reusable Fraud Decision Engine Subsystem.
"""

from app.decision.engine import FraudDecisionEngine, get_decision_engine
from app.decision.models import (
    DecisionAction,
    DecisionContext,
    FraudDecisionOutcome,
    RuleEvaluationResult,
    RuleSeverity,
)
from app.decision.rules import (
    AmountSpikeRule,
    AuthenticationFailureRule,
    BaseDecisionRule,
    DeviceTrustRule,
    DiurnalTimingRule,
    GraphCollusionRule,
    IPHoppingRule,
    MLScoreThresholdRule,
    VelocityBurstRule,
)
from app.decision.storage import PostgresDecisionStorage

__all__ = [
    "AmountSpikeRule",
    "AuthenticationFailureRule",
    "BaseDecisionRule",
    "DecisionAction",
    "DecisionContext",
    "DeviceTrustRule",
    "DiurnalTimingRule",
    "FraudDecisionEngine",
    "FraudDecisionOutcome",
    "GraphCollusionRule",
    "IPHoppingRule",
    "MLScoreThresholdRule",
    "PostgresDecisionStorage",
    "RuleEvaluationResult",
    "RuleSeverity",
    "VelocityBurstRule",
    "get_decision_engine",
]
