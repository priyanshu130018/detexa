"""
app/api/v1/endpoints/alerts.py
─────────────────────────────────────────────────────────────────────────────
Fraud & Security Alerts REST API endpoints.
"""

import math
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    PaginationParams,
    get_alert_service,
    get_current_user,
    get_db,
)
from app.db.models import User
from app.models.schemas import (
    AlertAssignRequest,
    AlertDetailOut,
    AlertOut,
    AlertResolutionRequest,
    AlertStatusUpdate,
    DashboardStats,
    PaginatedResponse,
)
from app.repositories.alert_repo import FraudAlertRepository
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts & Incident Triage"])


@router.get(
    "",
    response_model=PaginatedResponse[AlertOut],
    summary="List & Filter Alerts",
    description="Retrieve paginated fraud and security alerts with filters for status, risk level, and assigned analyst.",
)
def list_alerts(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None, description="Filter by status (open, reviewed, resolved, false_positive)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk category (Low, Medium, High)"),
    alert_type: Optional[str] = Query(None, description="Filter by alert type (credit_fraud, behavior_anomaly)"),
    assigned_to: Optional[uuid.UUID] = Query(None, description="Filter by assigned analyst UUID"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> PaginatedResponse[AlertOut]:
    repo = FraudAlertRepository(db)
    items, total = repo.list_filtered(
        skip=pagination.skip,
        limit=pagination.limit,
        status=status,
        risk_level=risk_level,
        alert_type=alert_type,
        assigned_to=assigned_to,
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
    response_model=DashboardStats,
    summary="Alerts & Dashboard Statistics",
    description="Retrieve high-level dashboard metrics, fraud counts, and open alerts.",
)
def get_alerts_stats(
    alert_svc: AlertService = Depends(get_alert_service),
    _: User = Depends(get_current_user),
) -> DashboardStats:
    return alert_svc.get_dashboard_stats()


@router.get(
    "/{alert_id}",
    response_model=AlertDetailOut,
    summary="Get Alert by ID",
    description="Retrieve comprehensive alert details including linked transaction, prediction SHAP drivers, and assigned analyst.",
)
def get_alert(
    alert_id: uuid.UUID = Path(..., description="Target Alert UUID"),
    alert_svc: AlertService = Depends(get_alert_service),
    _: User = Depends(get_current_user),
) -> AlertDetailOut:
    return alert_svc.get_alert_by_id(alert_id)


@router.patch(
    "/{alert_id}/status",
    response_model=AlertOut,
    summary="Update Alert Status (PATCH)",
    description="Transition alert triage status (open, reviewed, resolved, false_positive) with automatic audit logging.",
)
def update_alert_status_patch(
    alert_id: uuid.UUID = Path(..., description="Target Alert UUID"),
    body: AlertStatusUpdate = ...,
    alert_svc: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
) -> AlertOut:
    return alert_svc.update_alert_status(alert_id=alert_id, new_status=body.status, admin_user_id=current_user.id)


@router.put(
    "/{alert_id}/status",
    response_model=AlertOut,
    summary="Update Alert Status (PUT)",
    description="PUT compatibility endpoint for transition alert triage status.",
)
def update_alert_status_put(
    alert_id: uuid.UUID = Path(..., description="Target Alert UUID"),
    body: AlertStatusUpdate = ...,
    alert_svc: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
) -> AlertOut:
    return alert_svc.update_alert_status(alert_id=alert_id, new_status=body.status, admin_user_id=current_user.id)


@router.patch(
    "/{alert_id}/assign",
    response_model=AlertOut,
    summary="Assign Alert to Analyst",
    description="Assign an open alert to a specific security analyst for investigation.",
)
def assign_alert(
    alert_id: uuid.UUID = Path(..., description="Target Alert UUID"),
    body: AlertAssignRequest = ...,
    alert_svc: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
) -> AlertOut:
    alert = alert_svc.get_alert_by_id(alert_id)
    return alert_svc.update_alert_status(
        alert_id=alert_id,
        new_status=alert.status.value,
        assigned_to=body.assigned_to,
        admin_user_id=current_user.id,
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=AlertOut,
    summary="Resolve Alert",
    description="Complete investigation and resolve the alert with mandatory findings and rationale notes.",
)
def resolve_alert(
    alert_id: uuid.UUID = Path(..., description="Target Alert UUID"),
    body: AlertResolutionRequest = ...,
    alert_svc: AlertService = Depends(get_alert_service),
    current_user: User = Depends(get_current_user),
) -> AlertOut:
    return alert_svc.update_alert_status(
        alert_id=alert_id,
        new_status=body.status,
        resolution_notes=body.resolution_notes,
        admin_user_id=current_user.id,
    )
