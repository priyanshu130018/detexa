"""
app/decision/models.py
─────────────────────────────────────────────────────────────────────────────
Data models and contracts for the Detexa Fraud Decision Engine.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class DecisionAction(str, Enum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"  # Step-up authentication (MFA / 3D-Secure / OTP)
    REVIEW = "REVIEW"        # Manual Analyst Investigation Queue
    BLOCK = "BLOCK"          # Immediate Rejection / Authorization Decline


class RuleSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class RuleEvaluationResult:
    """Individual rule execution outcome."""
    rule_id: str
    rule_name: str
    triggered: bool
    severity: RuleSeverity
    action: DecisionAction
    reason_code: str
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DecisionContext:
    """
    Unified input payload supplied to the decision engine.
    Completely decouples ML model inference from business rule logic.
    """
    fraud_score: float
    amount: float
    currency: str = "INR"
    merchant: str = "Indian Merchant"
    category: str = "General"
    country: str = "IN"
    user_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    # Real-time sliding window features (from Redis)
    realtime_features: Dict[str, Any] = field(default_factory=dict)
    # Graph risk features (from Neo4j)
    graph_risk: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())


@dataclass
class FraudDecisionOutcome:
    """
    Final synthesized decision outcome.
    """
    decision: DecisionAction
    risk_level: str  # Low, Medium, High
    fraud_score: float
    primary_reason: str
    reason_codes: List[str]
    rules_triggered: List[RuleEvaluationResult]
    requires_step_up_auth: bool
    context: Optional[DecisionContext] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "risk_level": self.risk_level,
            "fraud_score": round(self.fraud_score, 4),
            "primary_reason": self.primary_reason,
            "reason_codes": self.reason_codes,
            "requires_step_up_auth": self.requires_step_up_auth,
            "rules_triggered_count": len(self.rules_triggered),
            "rules_triggered": [
                {
                    "rule_id": r.rule_id,
                    "rule_name": r.rule_name,
                    "severity": r.severity.value,
                    "action": r.action.value,
                    "reason_code": r.reason_code,
                    "message": r.message,
                }
                for r in self.rules_triggered
            ],
            "evaluated_at": self.evaluated_at.isoformat(),
        }
