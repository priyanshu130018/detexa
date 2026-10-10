"""
app/services/decision_service.py
─────────────────────────────────────────────────────────────────────────────
AI Decision governance, override tracking, and audit trail orchestration.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundException, ValidationError
from app.db.models import AuditLog, DecisionType, FraudPrediction, RiskLevel
from app.models.schemas import DecisionStatsOut
from app.repositories.audit_repo import AuditRepository
from app.repositories.prediction_repo import FraudPredictionRepository


class DecisionService:
    def __init__(self, db: Session):
        self.db = db
        self.pred_repo = FraudPredictionRepository(db)
        self.audit_repo = AuditRepository(db)

    def list_decisions(
        self,
        skip: int = 0,
        limit: int = 50,
        decision: Optional[str] = None,
        risk_level: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Tuple[List[FraudPrediction], int]:
        return self.pred_repo.list_filtered(
            skip=skip,
            limit=limit,
            decision=decision,
            risk_level=risk_level,
            endpoint=endpoint,
            model_version=model_version,
        )

    def get_decision(self, decision_id: uuid.UUID) -> FraudPrediction:
        decision = self.pred_repo.get_with_relations(decision_id)
        if not decision:
            raise EntityNotFoundException("Decision", decision_id)
        return decision

    def override_decision(
        self,
        decision_id: uuid.UUID,
        new_decision_str: str,
        reason: str,
        analyst_id: uuid.UUID,
    ) -> FraudPrediction:
        decision = self.get_decision(decision_id)

        try:
            target_decision = DecisionType(new_decision_str.upper())
        except ValueError:
            valid = [d.value for d in DecisionType]
            raise ValidationError(f"Invalid decision '{new_decision_str}'. Must be one of {valid}")

        prev_decision = decision.decision.value

        try:
            decision.decision = target_decision
            # If overridden to BLOCK, adjust is_fraud flag accordingly
            if target_decision == DecisionType.BLOCK:
                decision.is_fraud = True
                if decision.transaction:
                    decision.transaction.is_fraud = True
                    decision.transaction.risk_level = RiskLevel.HIGH
            elif target_decision in (DecisionType.CHALLENGE, DecisionType.REVIEW):
                decision.is_fraud = False
                if decision.transaction:
                    decision.transaction.is_fraud = False
                    decision.transaction.risk_level = RiskLevel.MEDIUM
            elif target_decision == DecisionType.ALLOW:
                decision.is_fraud = False
                if decision.transaction:
                    decision.transaction.is_fraud = False
                    decision.transaction.risk_level = RiskLevel.LOW

            # Record security audit log
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=analyst_id,
                action="DECISION_OVERRIDDEN",
                entity_type="fraud_prediction",
                entity_id=str(decision.id),
                details={
                    "previous_decision": prev_decision,
                    "new_decision": target_decision.value,
                    "reason": reason,
                    "transaction_id": str(decision.transaction_id) if decision.transaction_id else None,
                },
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(audit)
            self.db.commit()
            self.db.refresh(decision)
        except Exception as exc:
            self.db.rollback()
            raise exc

        return decision

    def evaluate_decision(
        self,
        fraud_score: float,
        amount: float,
        currency: str = "INR",
        merchant: str = "Reliance Digital",
        category: str = "General",
        country: str = "IN",
        user_id: Optional[str] = None,
        transaction_ref: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        realtime_features: Optional[Dict[str, Any]] = None,
        graph_risk: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates business rules against context using FraudDecisionEngine."""
        from app.decision import DecisionContext, get_decision_engine

        ctx = DecisionContext(
            fraud_score=fraud_score,
            amount=amount,
            currency=currency,
            merchant=merchant,
            category=category,
            country=country,
            user_id=user_id,
            transaction_ref=transaction_ref,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            realtime_features=realtime_features or {},
            graph_risk=graph_risk or {},
        )
        engine = get_decision_engine()
        outcome = engine.evaluate(ctx)
        return outcome.to_dict()

    def get_decision_stats(self) -> DecisionStatsOut:
        from app.core.config import settings
        from app.core.redis import cache_get, cache_set
        from sqlalchemy import case

        cache_key = "stats:decisions"
        cached = cache_get(cache_key)
        if cached:
            return DecisionStatsOut(**cached)

        row = (
            self.db.query(
                func.count(FraudPrediction.id).label("total"),
                func.sum(case((FraudPrediction.decision == DecisionType.ALLOW, 1), else_=0)).label("allow"),
                func.sum(case((FraudPrediction.decision == DecisionType.CHALLENGE, 1), else_=0)).label("challenge"),
                func.sum(case((FraudPrediction.decision == DecisionType.REVIEW, 1), else_=0)).label("review"),
                func.sum(case((FraudPrediction.decision == DecisionType.BLOCK, 1), else_=0)).label("block"),
            ).first()
        )

        total = row.total or 0 if row else 0
        allow = int(row.allow or 0) if row else 0
        challenge = int(row.challenge or 0) if row else 0
        review = int(row.review or 0) if row else 0
        block = int(row.block or 0) if row else 0

        stats = DecisionStatsOut(
            total_decisions=total,
            allow_count=allow,
            challenge_count=challenge,
            review_count=review,
            block_count=block,
            allow_percentage=round((allow / total) * 100, 2) if total else 0.0,
            challenge_percentage=round((challenge / total) * 100, 2) if total else 0.0,
            review_percentage=round((review / total) * 100, 2) if total else 0.0,
            block_percentage=round((block / total) * 100, 2) if total else 0.0,
        )
        cache_set(cache_key, stats.model_dump(), ttl_seconds=settings.redis_cache_ttl_stats)
        return stats

