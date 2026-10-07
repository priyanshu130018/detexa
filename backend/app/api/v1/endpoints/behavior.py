"""
app/api/v1/endpoints/behavior.py
─────────────────────────────────────────────────────────────────────────────
Behavioral Analytics and Session Telemetry REST API endpoints.
"""

import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import PaginationParams, get_behavior_service, get_current_user, get_db
from app.db.models import User
from app.models.schemas import BehaviorLogOut, BehaviorStatsOut, PaginatedResponse
from app.repositories.behavior_repo import BehaviorRepository
from app.services.behavior_service import BehaviorDetectionService

router = APIRouter(prefix="/behavior", tags=["Behavioral Analytics"])


@router.get(
    "/logs",
    response_model=PaginatedResponse[BehaviorLogOut],
    summary="List Behavioral Session Logs",
    description="Retrieve paginated session behavioral metrics (keystroke cadence, mouse velocity, VPN/TOR indicators).",
)
def list_behavior_logs(
    pagination: PaginationParams = Depends(),
    risk_level: Optional[str] = Query(None, description="Filter by risk category: Low, Medium, High"),
    is_vpn: Optional[bool] = Query(None, description="Filter by VPN indicator"),
    is_tor: Optional[bool] = Query(None, description="Filter by TOR indicator"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by user UUID"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[BehaviorLogOut]:
    repo = BehaviorRepository(db)
    items, total = repo.list_filtered(
        skip=pagination.skip,
        limit=pagination.limit,
        risk_level=risk_level,
        user_id=user_id,
        is_vpn=is_vpn,
        is_tor=is_tor,
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
    "/logs/{log_id}",
    response_model=BehaviorLogOut,
    summary="Get Behavior Log by ID",
    description="Retrieve detailed behavioral telemetry for a specific session log.",
)
def get_behavior_log(
    log_id: uuid.UUID = Path(..., description="Target Behavior Log UUID"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> BehaviorLogOut:
    repo = BehaviorRepository(db)
    log_rec = repo.get_with_relations(log_id)
    if not log_rec:
        from app.core.exceptions import EntityNotFoundException
        raise EntityNotFoundException("BehaviorLog", log_id)
    return log_rec


@router.get(
    "/stats",
    response_model=BehaviorStatsOut,
    summary="Behavioral Analytics Summary Stats",
    description="Retrieve aggregate anomaly metrics across all monitored sessions.",
)
def behavior_stats(
    behavior_svc: BehaviorDetectionService = Depends(get_behavior_service),
    _: User = Depends(get_current_user),
) -> BehaviorStatsOut:
    return BehaviorStatsOut(**behavior_svc.get_behavior_stats())
