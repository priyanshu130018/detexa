"""
app/streaming/decision_engine.py
─────────────────────────────────────────────────────────────────────────────
Real-time rule & ML decision engine combining deterministic security policies,
streaming velocity thresholds, and ML probability scores.
"""

from typing import List, Tuple

from app.core.config import settings
from app.db.models import DecisionType, RiskLevel
from app.streaming.event_schemas import AggregatedFeatures, TransactionPayload


class RealTimeDecisionEngine:
    """
    Evaluates real-time business rules, velocity state, and ML risk scores
    to output deterministic automated verdicts: ALLOW, REVIEW, or BLOCK.
    """

    def __init__(
        self,
        fraud_threshold: float = settings.fraud_threshold,
        high_risk_threshold: float = settings.high_risk_threshold,
    ):
        self.fraud_threshold = fraud_threshold
        self.high_risk_threshold = high_risk_threshold

    def evaluate(
        self,
        payload: TransactionPayload,
        features: AggregatedFeatures,
        ml_fraud_score: float,
        is_tor: bool = False,
        is_vpn: bool = False,
    ) -> Tuple[DecisionType, RiskLevel, List[str]]:
        """
        Evaluate composite rules against transaction payload and streaming features.
        Returns: (DecisionType, RiskLevel, List[reason_codes])
        """
        reasons: List[str] = []
        is_blocked = False
        is_review = False

        # ── Tier 1: Deterministic Hard Rules (Highest Precedence) ────────────

        # Rule 1: High Velocity Spike (Card cracking / automated bot scripts)
        if features.velocity_1m >= 5:
            reasons.append("RULE_BURST_VELOCITY_1M_EXCEEDED")
            is_blocked = True
        elif features.velocity_5m >= 12:
            reasons.append("RULE_VELOCITY_5M_ELEVATED")
            is_review = True

        # Rule 2: TOR Exit Node with significant transaction amount
        if is_tor and payload.amount > 200.0:
            reasons.append("RULE_TOR_NETWORK_HIGH_VALUE")
            is_blocked = True
        elif is_tor:
            reasons.append("RULE_TOR_NETWORK_DETECTED")
            is_review = True

        # Rule 3: Cross-Border Geolocation Mismatch with high value
        if features.is_foreign_transaction and payload.amount > 1500.0:
            reasons.append("RULE_CROSS_BORDER_HIGH_AMOUNT")
            is_review = True

        # Rule 4: Extreme Amount Spike Relative to User's 1-Hour Moving Average
        if features.amount_deviation_ratio > 4.5 and payload.amount > 1000.0:
            reasons.append("RULE_AMOUNT_DEVIATION_SPIKE")
            is_review = True

        # Rule 5: Micro-Charge Card Testing Pattern
        if 0.0 < payload.amount < 1.50 and features.velocity_5m >= 3:
            reasons.append("RULE_CARD_TESTING_MICRO_CHARGE")
            is_review = True

        # ── Tier 2: Machine Learning Probability Evaluation ─────────────────

        if ml_fraud_score >= self.high_risk_threshold:
            reasons.append(f"ML_HIGH_FRAUD_PROBABILITY_{ml_fraud_score:.2f}")
            is_blocked = True
        elif ml_fraud_score >= self.fraud_threshold:
            reasons.append(f"ML_SUSPICIOUS_RISK_SCORE_{ml_fraud_score:.2f}")
            is_review = True
        else:
            reasons.append("ML_LOW_RISK_NORMAL")

        # ── Tier 3: Final Decision Synthesis ─────────────────────────────────

        if is_blocked:
            decision = DecisionType.BLOCK
            risk = RiskLevel.HIGH
        elif is_review:
            decision = DecisionType.REVIEW
            risk = RiskLevel.MEDIUM
        else:
            decision = DecisionType.ALLOW
            risk = RiskLevel.LOW

        return decision, risk, reasons
