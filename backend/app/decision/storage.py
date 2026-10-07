"""
app/decision/storage.py
─────────────────────────────────────────────────────────────────────────────
PostgreSQL Decision Persistence Handler.
Atomically records decisions, reason codes, fraud predictions, alerts, and audit trails.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import (
    AlertStatus,
    AuditLog,
    DecisionType,
    FraudAlert,
    FraudPrediction,
    RiskLevel,
    Transaction,
)
from app.decision.models import DecisionAction, FraudDecisionOutcome


class PostgresDecisionStorage:
    """
    Persists decision engine outcomes to normalized PostgreSQL tables.
    """

    @staticmethod
    def persist_decision(
        db: Session,
        outcome: FraudDecisionOutcome,
        txn: Transaction,
        endpoint: str = "/api/v1/predict/credit",
        input_hash: Optional[str] = None,
        latency_ms: float = 0.0,
        shap_drivers: Optional[List[Dict[str, Any]]] = None,
        explanation: Optional[Dict[str, Any]] = None,
        model_version: str = "2.0.0",
    ) -> FraudPrediction:
        """
        Executes atomic database writes for the evaluated decision outcome.
        """
        risk_enum = RiskLevel(outcome.risk_level)
        decision_enum = DecisionType(outcome.decision.value)
        is_fraud = (outcome.decision == DecisionAction.BLOCK)

        # 1. Update Transaction record
        txn.risk_level = risk_enum
        txn.fraud_score = outcome.fraud_score
        txn.is_fraud = is_fraud
        txn.label = int(is_fraud)

        # 2. Insert FraudPrediction
        prediction_id = uuid.uuid4()
        pred = FraudPrediction(
            id=prediction_id,
            transaction_id=txn.id,
            endpoint=endpoint,
            input_hash=input_hash or str(uuid.uuid4()),
            fraud_score=outcome.fraud_score,
            anomaly_score=None,
            risk_level=risk_enum,
            is_fraud=is_fraud,
            decision=decision_enum,
            shap_values=shap_drivers,
            latency_ms=round(latency_ms, 2),
            model_version=model_version,
            created_at=datetime.now(timezone.utc),
        )
        db.add(pred)
        db.flush()

        # 3. Create FraudAlert for Non-ALLOW Decisions (BLOCK, REVIEW, CHALLENGE)
        if outcome.decision != DecisionAction.ALLOW:
            alert_meta = {
                "decision": outcome.decision.value,
                "reason_codes": outcome.reason_codes,
                "requires_step_up_auth": outcome.requires_step_up_auth,
                "triggered_rules": [r.rule_id for r in outcome.rules_triggered],
                "merchant": txn.merchant,
                "amount": txn.amount,
            }
            if explanation:
                alert_meta["explanation"] = explanation

            alert = FraudAlert(
                id=uuid.uuid4(),
                user_id=txn.user_id,
                transaction_id=txn.id,
                prediction_id=pred.id,
                alert_type="fraud_decision_engine",
                risk_level=risk_enum,
                score=outcome.fraud_score,
                description=f"[{outcome.decision.value}] {outcome.primary_reason}",
                status=AlertStatus.OPEN,
                shap_values=shap_drivers,
                metadata_=alert_meta,
                created_at=datetime.now(timezone.utc),
            )
            db.add(alert)

        # 4. Insert AuditLog
        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=txn.user_id,
            action=f"DECISION_{outcome.decision.value}",
            entity_type="transaction",
            entity_id=str(txn.id),
            ip_address=outcome.context.ip_address if outcome.context else None,
            details={
                "decision": outcome.decision.value,
                "primary_reason": outcome.primary_reason,
                "reason_codes": outcome.reason_codes,
                "fraud_score": outcome.fraud_score,
                "risk_level": outcome.risk_level,
                "rules_count": len(outcome.rules_triggered),
            },
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit)

        return pred
