"""
app/decision/engine.py
─────────────────────────────────────────────────────────────────────────────
Reusable Fraud Decision Engine.

Arbitrates business rules, real-time streaming counters, Neo4j graph signals,
and ML fraud scores to produce deterministic decisions:
- ALLOW: Seamless transaction clearance.
- CHALLENGE: Step-up authentication required (MFA / 3D-Secure / OTP).
- REVIEW: High-risk anomaly routed to fraud analyst triage queue.
- BLOCK: Immediate authorization decline.

Strictly decouples model scoring from business decision logic.
"""

from typing import List, Optional

from app.core.logging import logger
from app.decision.models import (
    DecisionAction,
    DecisionContext,
    FraudDecisionOutcome,
    RuleEvaluationResult,
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


class FraudDecisionEngine:
    """
    Enterprise Fraud Decision Engine.
    Executes ordered rule policies and priority arbitration.
    """

    def __init__(self, custom_rules: Optional[List[BaseDecisionRule]] = None):
        self.rules: List[BaseDecisionRule] = custom_rules or [
            VelocityBurstRule(),
            AuthenticationFailureRule(),
            AmountSpikeRule(),
            DeviceTrustRule(),
            IPHoppingRule(),
            GraphCollusionRule(),
            DiurnalTimingRule(),
            MLScoreThresholdRule(),
        ]

    def evaluate(self, context: DecisionContext) -> FraudDecisionOutcome:
        """
        Evaluates context across all configured rules and synthesizes final decision.
        """
        triggered_results: List[RuleEvaluationResult] = []

        for rule in self.rules:
            try:
                res = rule.evaluate(context)
                if res is not None and res.triggered:
                    triggered_results.append(res)
            except Exception as exc:
                logger.error(f"Error evaluating rule {rule.rule_id}: {exc}")

        # ── Priority Arbitration ─────────────────────────────────────────────
        # Priority Order: BLOCK > REVIEW > CHALLENGE > ALLOW
        has_block = any(r.action == DecisionAction.BLOCK for r in triggered_results)
        has_review = any(r.action == DecisionAction.REVIEW for r in triggered_results)
        has_challenge = any(r.action == DecisionAction.CHALLENGE for r in triggered_results)

        if has_block:
            final_decision = DecisionAction.BLOCK
            risk_level = "High"
            requires_step_up = False
        elif has_review:
            final_decision = DecisionAction.REVIEW
            risk_level = "High" if context.fraud_score >= 0.70 else "Medium"
            requires_step_up = False
        elif has_challenge:
            final_decision = DecisionAction.CHALLENGE
            risk_level = "Medium"
            requires_step_up = True
        else:
            final_decision = DecisionAction.ALLOW
            risk_level = "Low"
            requires_step_up = False

        # Extract reason codes
        reason_codes = [r.reason_code for r in triggered_results if r.reason_code]
        if not reason_codes:
            reason_codes = ["ML_LOW_RISK_NORMAL"]

        # Primary reason synthesis
        if has_block:
            primary_rule = next(r for r in triggered_results if r.action == DecisionAction.BLOCK)
            primary_reason = primary_rule.message
        elif has_review:
            primary_rule = next(r for r in triggered_results if r.action == DecisionAction.REVIEW)
            primary_reason = primary_rule.message
        elif has_challenge:
            primary_rule = next(r for r in triggered_results if r.action == DecisionAction.CHALLENGE)
            primary_reason = primary_rule.message
        else:
            primary_reason = f"Normal transaction profile (Score: {context.fraud_score:.3f}; all risk checks passed)."

        return FraudDecisionOutcome(
            decision=final_decision,
            risk_level=risk_level,
            fraud_score=context.fraud_score,
            primary_reason=primary_reason,
            reason_codes=reason_codes,
            rules_triggered=triggered_results,
            requires_step_up_auth=requires_step_up,
            context=context,
        )


_decision_engine_instance: Optional[FraudDecisionEngine] = None


def get_decision_engine() -> FraudDecisionEngine:
    """Returns singleton instance of FraudDecisionEngine."""
    global _decision_engine_instance
    if _decision_engine_instance is None:
        _decision_engine_instance = FraudDecisionEngine()
    return _decision_engine_instance
