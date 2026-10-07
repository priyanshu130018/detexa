"""
app/decision/rules.py
─────────────────────────────────────────────────────────────────────────────
Modular and configurable business rules for the Detexa Fraud Decision Engine.
Thresholds and policies are injected dynamically from centralized settings (.env).
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.config import settings
from app.decision.models import (
    DecisionAction,
    DecisionContext,
    RuleEvaluationResult,
    RuleSeverity,
)


class BaseDecisionRule(ABC):
    """Abstract base class for all business decision rules."""

    def __init__(self, rule_id: str, rule_name: str):
        self.rule_id = rule_id
        self.rule_name = rule_name

    @abstractmethod
    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        """Evaluates rule logic against context. Returns RuleEvaluationResult if triggered, else None."""
        pass


class VelocityBurstRule(BaseDecisionRule):
    """Evaluates rapid transaction velocity across sliding windows."""

    def __init__(self):
        super().__init__("RULE_VELOCITY", "Multi-Scale Transaction Velocity")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        v1m = int(rf.get("velocity_1m", 1))
        v5m = int(rf.get("velocity_5m", 1))

        if v1m >= settings.rule_max_velocity_1m:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.CRITICAL,
                action=DecisionAction.BLOCK,
                reason_code=f"BURST_VELOCITY_1M_EXCEEDED_{v1m}",
                message=f"Transaction velocity burst detected ({v1m} txns in 1 minute; limit: {settings.rule_max_velocity_1m}).",
                metadata={"velocity_1m": v1m, "threshold": settings.rule_max_velocity_1m},
            )
        elif v5m >= settings.rule_max_velocity_5m:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.REVIEW,
                reason_code=f"ELEVATED_VELOCITY_5M_{v5m}",
                message=f"Elevated velocity detected ({v5m} txns in 5 minutes; threshold: {settings.rule_max_velocity_5m}).",
                metadata={"velocity_5m": v5m, "threshold": settings.rule_max_velocity_5m},
            )
        return None


class AuthenticationFailureRule(BaseDecisionRule):
    """Evaluates failed authorization attempts and consecutive decline streaks."""

    def __init__(self):
        super().__init__("RULE_AUTH_FAIL", "Authentication & Decline Streak Tracking")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        failed_5m = int(rf.get("failed_auth_5m", 0))
        consecutive = int(rf.get("consecutive_failures", 0))

        if failed_5m >= settings.rule_max_failed_auth_5m or consecutive >= 4:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.CRITICAL,
                action=DecisionAction.BLOCK,
                reason_code=f"EXCESSIVE_AUTH_FAILURES_{failed_5m}",
                message=f"Excessive authentication/authorization failures ({failed_5m} in 5 minutes).",
                metadata={"failed_5m": failed_5m, "consecutive": consecutive},
            )
        elif failed_5m >= 2 or consecutive >= 2:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.CHALLENGE,
                reason_code=f"REPEAT_DECLINES_CHALLENGE_{failed_5m}",
                message=f"Multiple recent declines ({failed_5m}); step-up authentication required.",
                metadata={"failed_5m": failed_5m, "consecutive": consecutive},
            )
        return None


class AmountSpikeRule(BaseDecisionRule):
    """Evaluates monetary spending spikes and deviation from historical baselines."""

    def __init__(self):
        super().__init__("RULE_AMOUNT", "Monetary Spike & Deviation Detection")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        deviation = float(rf.get("amount_deviation_ratio", 1.0))

        if ctx.amount >= settings.rule_max_amount_hard_limit:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.REVIEW,
                reason_code=f"HARD_AMOUNT_LIMIT_EXCEEDED_${ctx.amount:.0f}",
                message=f"High-value transaction (${ctx.amount:.2f}) exceeds policy ceiling (${settings.rule_max_amount_hard_limit:.0f}).",
                metadata={"amount": ctx.amount, "threshold": settings.rule_max_amount_hard_limit},
            )
        elif deviation >= settings.rule_max_amount_deviation and ctx.amount > 300.0:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.CHALLENGE,
                reason_code=f"AMOUNT_DEVIATION_SPIKE_{deviation:.1f}X",
                message=f"Monetary deviation ({deviation:.1f}x historical mean); step-up auth triggered.",
                metadata={"deviation": deviation, "amount": ctx.amount},
            )
        return None


class DeviceTrustRule(BaseDecisionRule):
    """Evaluates hardware fingerprint switching and trusted device status."""

    def __init__(self):
        super().__init__("RULE_DEVICE", "Hardware Fingerprint & Trust Verification")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        distinct_devs = int(rf.get("distinct_devices_15m", 1))
        dev_changed = bool(rf.get("device_changed", False))

        if distinct_devs >= 3:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.CRITICAL,
                action=DecisionAction.BLOCK,
                reason_code=f"RAPID_DEVICE_HOPPING_{distinct_devs}",
                message=f"Suspicious rapid hardware switching ({distinct_devs} devices in 15m).",
                metadata={"distinct_devices_15m": distinct_devs},
            )
        elif dev_changed and settings.rule_enable_device_change_challenge and ctx.amount > 150.0:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.CHALLENGE,
                reason_code="NEW_DEVICE_STEP_UP_AUTH",
                message="Unrecognized device detected for elevated transaction; MFA step-up challenge required.",
                metadata={"amount": ctx.amount},
            )
        return None


class IPHoppingRule(BaseDecisionRule):
    """Evaluates rapid proxy switching and network hopping."""

    def __init__(self):
        super().__init__("RULE_IP_HOP", "IP Address & Network Stability")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        distinct_ips = int(rf.get("distinct_ips_15m", 1))
        ip_changed = bool(rf.get("ip_changed", False))

        if distinct_ips >= 3:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.REVIEW,
                reason_code=f"EXCESSIVE_IP_HOPPING_{distinct_ips}",
                message=f"Multiple IP addresses detected ({distinct_ips} in 15m).",
                metadata={"distinct_ips_15m": distinct_ips},
            )
        elif ip_changed and settings.rule_enable_ip_hopping_challenge and ctx.amount > 200.0:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.INFO,
                action=DecisionAction.CHALLENGE,
                reason_code="IP_CHANGE_CHALLENGE",
                message="IP address changed on high-value transaction; step-up verification required.",
                metadata={"amount": ctx.amount},
            )
        return None


class GraphCollusionRule(BaseDecisionRule):
    """Evaluates Neo4j graph entity sharing and collusion fraud rings."""

    def __init__(self):
        super().__init__("RULE_GRAPH", "Neo4j Graph Relationship & Ring Detection")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        gr = ctx.graph_risk
        shared_users = int(gr.get("graph_shared_device_users", 1))
        graph_risk_score = float(gr.get("graph_risk_score", 0.0))
        shared_frauds = int(gr.get("graph_shared_device_frauds", 0))

        if shared_users >= settings.rule_max_graph_shared_users or shared_frauds >= 2:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.CRITICAL,
                action=DecisionAction.BLOCK,
                reason_code=f"GRAPH_SHARED_DEVICE_COLLUSION_{shared_users}_USERS",
                message=f"Hardware device linked to {shared_users} distinct accounts with {shared_frauds} confirmed frauds.",
                metadata={"shared_users": shared_users, "shared_frauds": shared_frauds},
            )
        elif graph_risk_score >= settings.rule_max_graph_risk_score:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.CHALLENGE,
                reason_code=f"GRAPH_NETWORK_RISK_{graph_risk_score:.2f}",
                message=f"Elevated graph topological risk ({graph_risk_score:.2f}); step-up authentication required.",
                metadata={"graph_risk_score": graph_risk_score},
            )
        return None


class DiurnalTimingRule(BaseDecisionRule):
    """Evaluates off-peak nocturnal hours against monetary thresholds."""

    def __init__(self):
        super().__init__("RULE_DIURNAL", "Diurnal & Nocturnal Timing Analysis")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        rf = ctx.realtime_features
        is_unusual = bool(rf.get("is_unusual_hour", False))
        hour = float(rf.get("hour_of_day", 12.0))

        if (is_unusual or (hour >= 2.0 and hour <= 5.0)) and ctx.amount > settings.rule_off_peak_night_threshold:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.INFO,
                action=DecisionAction.CHALLENGE,
                reason_code=f"OFF_PEAK_NIGHT_TRANSACTION_{hour:.1f}H",
                message=f"High-value transaction (${ctx.amount:.2f}) executed during off-peak hours ({hour:.1f}h UTC).",
                metadata={"hour": hour, "amount": ctx.amount},
            )
        return None


class MLScoreThresholdRule(BaseDecisionRule):
    """Evaluates pure ML model probability score tiers."""

    def __init__(self):
        super().__init__("RULE_ML_SCORE", "Machine Learning Model Probability")

    def evaluate(self, ctx: DecisionContext) -> Optional[RuleEvaluationResult]:
        score = ctx.fraud_score

        if score >= settings.decision_threshold_review:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.CRITICAL,
                action=DecisionAction.BLOCK,
                reason_code=f"ML_CRITICAL_FRAUD_SCORE_{score:.3f}",
                message=f"ML predicted critical fraud probability ({score:.3f} >= {settings.decision_threshold_review}).",
                metadata={"score": score, "threshold": settings.decision_threshold_review},
            )
        elif score >= settings.decision_threshold_challenge:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.WARNING,
                action=DecisionAction.REVIEW,
                reason_code=f"ML_HIGH_RISK_MANUAL_REVIEW_{score:.3f}",
                message=f"ML predicted elevated fraud probability ({score:.3f} >= {settings.decision_threshold_challenge}).",
                metadata={"score": score, "threshold": settings.decision_threshold_challenge},
            )
        elif score >= settings.decision_threshold_allow:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.INFO,
                action=DecisionAction.CHALLENGE,
                reason_code=f"ML_MODERATE_RISK_CHALLENGE_{score:.3f}",
                message=f"ML predicted moderate fraud probability ({score:.3f} >= {settings.decision_threshold_allow}); step-up authentication required.",
                metadata={"score": score, "threshold": settings.decision_threshold_allow},
            )
        else:
            return RuleEvaluationResult(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                triggered=True,
                severity=RuleSeverity.INFO,
                action=DecisionAction.ALLOW,
                reason_code="ML_LOW_RISK_NORMAL",
                message=f"ML predicted low fraud probability ({score:.3f} < {settings.decision_threshold_allow}).",
                metadata={"score": score, "threshold": settings.decision_threshold_allow},
            )
