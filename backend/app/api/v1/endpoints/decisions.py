"""
app/api/v1/endpoints/decisions.py
─────────────────────────────────────────────────────────────────────────────
AI Decisions & Override Management REST API endpoints.
"""

import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_current_admin_user,
    get_current_user,
    get_db,
    get_decision_service,
)
from app.db.models import User
from app.models.schemas import (
    DecisionOut,
    DecisionOverrideRequest,
    DecisionStatsOut,
    PaginatedResponse,
)
from app.services.decision_service import DecisionService

router = APIRouter(prefix="/decisions", tags=["Decisions & AI Governance"])


@router.get(
    "",
    response_model=PaginatedResponse[DecisionOut],
    summary="List AI Decisions",
    description="Retrieve paginated log of ML inference decisions (ALLOW, REVIEW, BLOCK) with filters.",
)
def list_decisions(
    pagination: PaginationParams = Depends(),
    decision: Optional[str] = Query(None, description="Filter by decision type: ALLOW, REVIEW, BLOCK"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category: Low, Medium, High"),
    endpoint: Optional[str] = Query(None, description="Filter by inference endpoint"),
    model_version: Optional[str] = Query(None, description="Filter by model version"),
    decision_svc: DecisionService = Depends(get_decision_service),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[DecisionOut]:
    items, total = decision_svc.list_decisions(
        skip=pagination.skip,
        limit=pagination.limit,
        decision=decision,
        risk_level=risk_level,
        endpoint=endpoint,
        model_version=model_version,
    )
    pages = math.ceil(total / pagination.page_size) if total > 0 else 1

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=pages,
        has_next=pagination.page < pages,
        has_prev=pagination.page > 1,
    )


@router.get(
    "/stats",
    response_model=DecisionStatsOut,
    summary="Decision Statistics Summary",
    description="Retrieve aggregate counts and percentage breakdown for ALLOW, REVIEW, and BLOCK decisions.",
)
def get_decision_stats(
    decision_svc: DecisionService = Depends(get_decision_service),
    _: User = Depends(get_current_user),
) -> DecisionStatsOut:
    return decision_svc.get_decision_stats()


@router.get(
    "/{decision_id}",
    response_model=DecisionOut,
    summary="Get Decision by ID",
    description="Retrieve specific prediction decision details with linked transaction record.",
)
def get_decision(
    decision_id: uuid.UUID = Path(..., description="Target Decision UUID"),
    decision_svc: DecisionService = Depends(get_decision_service),
    _: User = Depends(get_current_user),
) -> DecisionOut:
    return decision_svc.get_decision(decision_id)


@router.post(
    "/{decision_id}/override",
    response_model=DecisionOut,
    summary="Override AI Decision (Analyst/Admin Only)",
    description="Manually override an automated model decision (e.g., flip from BLOCK to ALLOW or vice versa) with mandatory audit justification.",
)
def override_decision(
    decision_id: uuid.UUID = Path(..., description="Target Decision UUID"),
    body: DecisionOverrideRequest = ...,
    decision_svc: DecisionService = Depends(get_decision_service),
    current_user: User = Depends(get_current_user),
) -> DecisionOut:
    return decision_svc.override_decision(
        decision_id=decision_id,
        new_decision_str=body.new_decision,
        reason=body.reason,
        analyst_id=current_user.id,
    )


@router.post(
    "/evaluate/context",
    summary="Evaluate Fraud Decision Rules against Context",
    description="Simulates/evaluates the complete decision engine arbitration (ALLOW, CHALLENGE, REVIEW, BLOCK) on an input context.",
)
def evaluate_decision_context(
    fraud_score: float = Query(0.05, ge=0.0, le=1.0),
    amount: float = Query(2500.0, ge=0.0),
    currency: str = Query("INR"),
    merchant: str = Query("Reliance Digital"),
    category: str = Query("Electronics"),
    country: str = Query("IN"),
    user_id: Optional[str] = Query(None),
    device_fingerprint: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    decision_svc: DecisionService = Depends(get_decision_service),
    current_user: User = Depends(get_current_user),
):
    from app.feature_store import get_feature_store
    from app.graph import get_graph_service

    uid = user_id or str(current_user.id)
    redis_hot = get_feature_store().get_hot_features(
        user_key=uid,
        current_amount=amount,
        current_merchant=merchant,
        current_category=category,
        current_device=device_fingerprint,
        current_ip=ip_address,
        current_country=country,
    )
    graph_risk = get_graph_service().get_features(
        user_id=uid,
        current_device_fp=device_fingerprint,
        current_ip=ip_address,
    )

    return decision_svc.evaluate_decision(
        fraud_score=fraud_score,
        amount=amount,
        currency=currency,
        merchant=merchant,
        category=category,
        country=country,
        user_id=uid,
        device_fingerprint=device_fingerprint,
        ip_address=ip_address,
        realtime_features=redis_hot.to_dict(),
        graph_risk=graph_risk.to_dict(),
    )


@router.get(
    "/rules/policy",
    summary="Get Configured Decision Rules & Active Thresholds",
    description="Returns list of registered decision rules and active policy thresholds loaded from .env.",
)
def get_decision_rules_policy(
    current_user: User = Depends(get_current_user),
):
    from app.core.config import settings
    return {
        "thresholds": {
            "allow_bound": settings.decision_threshold_allow,
            "challenge_bound": settings.decision_threshold_challenge,
            "review_bound": settings.decision_threshold_review,
        },
        "rules": [
            {"id": "RULE_VELOCITY", "name": "Burst Velocity 1m/5m", "limits": {"1m": settings.rule_max_velocity_1m, "5m": settings.rule_max_velocity_5m}},
            {"id": "RULE_AUTH_FAIL", "name": "Failed Auth Streak", "limit_5m": settings.rule_max_failed_auth_5m},
            {"id": "RULE_AMOUNT", "name": "Amount Deviation Spike", "deviation_multiplier": settings.rule_max_amount_deviation, "hard_ceiling": settings.rule_max_amount_hard_limit},
            {"id": "RULE_DEVICE", "name": "Hardware Hopping / New Device", "challenge_enabled": settings.rule_enable_device_change_challenge},
            {"id": "RULE_IP_HOP", "name": "IP Hopping / Proxy", "challenge_enabled": settings.rule_enable_ip_hopping_challenge},
            {"id": "RULE_GRAPH", "name": "Neo4j Graph Collusion", "max_shared_users": settings.rule_max_graph_shared_users, "max_risk_score": settings.rule_max_graph_risk_score},
            {"id": "RULE_DIURNAL", "name": "Nocturnal Timing Window", "night_amount_threshold": settings.rule_off_peak_night_threshold},
            {"id": "RULE_ML_SCORE", "name": "Machine Learning Score Tiers", "allow": settings.decision_threshold_allow, "challenge": settings.decision_threshold_challenge, "review": settings.decision_threshold_review},
        ],
    }

