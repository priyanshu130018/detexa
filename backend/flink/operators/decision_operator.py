"""
flink/operators/decision_operator.py
─────────────────────────────────────────────────────────────────────────────
Real-time Stream Decision Operator for PyFlink pipelines.
Evaluates multi-tier policy rules against streaming window metrics and ML scores.
"""

from typing import List, Tuple

from flink.config import flink_config
from flink.models.state_schemas import FlinkEnrichedEvent


class DecisionOperator:
    """
    Evaluates streaming window state and ML probability score to output:
    (decision: str, risk_level: str, reason_codes: List[str])
    """

    def __init__(
        self,
        fraud_threshold: float = flink_config.fraud_threshold,
        high_risk_threshold: float = flink_config.high_risk_threshold,
    ):
        self.fraud_threshold = fraud_threshold
        self.high_risk_threshold = high_risk_threshold

    def evaluate(
        self,
        event: FlinkEnrichedEvent,
        ml_fraud_score: float,
    ) -> Tuple[str, str, List[str]]:
        wm = event.window_metrics
        reasons: List[str] = []
        is_blocked = False
        is_review = False

        # ── 1. Velocity & Frequency Rules ────────────────────────────────────
        if wm.velocity_1m >= 5:
            reasons.append("RULE_BURST_VELOCITY_1M_EXCEEDED")
            is_blocked = True
        elif wm.velocity_5m >= 12:
            reasons.append("RULE_ELEVATED_VELOCITY_5M")
            is_review = True

        # ── 2. Failed Transaction Burst Rule ─────────────────────────────────
        if wm.failed_txn_count_5m >= 3:
            reasons.append(f"RULE_CONSECUTIVE_AUTH_FAILURES_{wm.failed_txn_count_5m}")
            is_blocked = True
        elif wm.failed_txn_count_1h >= 5:
            reasons.append("RULE_EXCESSIVE_DECLINES_1H")
            is_review = True

        # ── 3. Unusual Transaction Timing (Nighttime 02:00-05:00) ────────────
        if wm.is_unusual_hour and event.amount > 500.0:
            reasons.append(f"RULE_UNUSUAL_TIMING_OFF_PEAK_{wm.hour_of_day:.1f}H")
            is_review = True

        # ── 4. Rapid Hardware & IP Switching ─────────────────────────────────
        if wm.distinct_devices_15m >= 3:
            reasons.append(f"RULE_RAPID_DEVICE_HOPPING_{wm.distinct_devices_15m}")
            is_blocked = True
        elif wm.device_changed and wm.velocity_5m >= 2:
            reasons.append("RULE_NEW_DEVICE_VELOCITY_BURST")
            is_review = True

        if wm.distinct_ips_15m >= 3:
            reasons.append(f"RULE_RAPID_IP_HOPPING_{wm.distinct_ips_15m}")
            is_review = True

        # ── 5. Monetary Spikes & Deviations ──────────────────────────────────
        if wm.amount_deviation_ratio > 4.5 and event.amount > 800.0:
            reasons.append(f"RULE_AMOUNT_DEVIATION_SPIKE_{wm.amount_deviation_ratio:.1f}X")
            is_review = True

        # ── 6. ML Model Probability Evaluation ───────────────────────────────
        if ml_fraud_score >= self.high_risk_threshold:
            reasons.append(f"ML_HIGH_RISK_SCORE_{ml_fraud_score:.2f}")
            is_blocked = True
        elif ml_fraud_score >= self.fraud_threshold:
            reasons.append(f"ML_ELEVATED_RISK_SCORE_{ml_fraud_score:.2f}")
            is_review = True
        else:
            reasons.append("ML_LOW_RISK_NORMAL")

        # ── Synthesis ────────────────────────────────────────────────────────
        if is_blocked:
            decision = "BLOCK"
            risk_level = "High"
        elif is_review:
            decision = "REVIEW"
            risk_level = "Medium"
        else:
            decision = "ALLOW"
            risk_level = "Low"

        return decision, risk_level, reasons
