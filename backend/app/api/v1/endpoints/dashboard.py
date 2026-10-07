"""
app/api/v1/endpoints/dashboard.py
─────────────────────────────────────────────────────────────────────────────
Dashboard Analytics & Business Intelligence REST API endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_dashboard_service
from app.db.models import User
from app.models.schemas import (
    CategoryRiskBreakdown,
    DashboardStats,
    GeoRiskPoint,
    RiskDistribution,
    TimeSeriesPoint,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard Analytics"])


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Dashboard Summary KPIs",
    description="Retrieve high-level KPIs: total transactions, fraud count, fraud rate, open alerts count, and average fraud score (cached in Redis).",
)
def get_dashboard_stats(
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    _: User = Depends(get_current_user),
) -> DashboardStats:
    return dashboard_svc.get_kpi_stats()


@router.get(
    "/trends",
    response_model=List[TimeSeriesPoint],
    summary="Transaction & Fraud Volume Time-Series Trends",
    description="Retrieve daily aggregated counts of total transactions, detected frauds, and average risk score over the specified lookback window.",
)
def get_trends(
    days: int = Query(30, ge=1, le=180, description="Lookback days for trend analysis"),
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    _: User = Depends(get_current_user),
) -> List[TimeSeriesPoint]:
    return dashboard_svc.get_time_series_trends(days=days)


@router.get(
    "/risk-distribution",
    response_model=RiskDistribution,
    summary="Risk Tier Distribution",
    description="Retrieve transaction distribution across Low, Medium, and High risk tiers.",
)
def get_risk_distribution(
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    _: User = Depends(get_current_user),
) -> RiskDistribution:
    return dashboard_svc.get_risk_distribution()


@router.get(
    "/categories",
    response_model=List[CategoryRiskBreakdown],
    summary="Risk Breakdown by Industry Category",
    description="Retrieve fraud volume and percentage rate broken down by merchant category.",
)
def get_category_risk(
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    _: User = Depends(get_current_user),
) -> List[CategoryRiskBreakdown]:
    return dashboard_svc.get_category_breakdown()


@router.get(
    "/geo",
    response_model=List[GeoRiskPoint],
    summary="Geographic Risk & Transaction Distribution",
    description="Retrieve transaction volume and fraud risk index by country for global threat mapping.",
)
def get_geo_risk(
    dashboard_svc: DashboardService = Depends(get_dashboard_service),
    _: User = Depends(get_current_user),
) -> List[GeoRiskPoint]:
    return dashboard_svc.get_geo_risk()
