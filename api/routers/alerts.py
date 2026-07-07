"""
api/routers/alerts.py
─────────────────────────────────────────────────────────────────────────────
GET  /alerts               – list alerts (filterable)
PUT  /alerts/{id}/status   – update alert status
GET  /alerts/stats         – dashboard aggregate statistics
GET  /alerts/transactions  – paginated transaction list
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.middleware.auth_middleware import get_current_user
from database.db import get_db
from database.models import User
from models.schemas import AlertOut, AlertUpdate, DashboardStats
from services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["Alerts"])

@router.get("", response_model=List[AlertOut])
def list_alerts(
    limit: int = Query(100, le=500),
    skip: int = 0,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return AlertService(db).list_alerts(limit, skip, status, risk_level)


@router.put("/{alert_id}/status", response_model=AlertOut)
def update_alert(
    alert_id: str,
    body: AlertUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return AlertService(db).update_alert_status(alert_id, body.status)


@router.get("/stats", response_model=DashboardStats)
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return AlertService(db).get_dashboard_stats()


@router.get("/transactions")
def list_transactions(
    limit: int = Query(200, le=1000),
    skip: int = 0,
    is_fraud: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    txns = AlertService(db).list_transactions(limit, skip, is_fraud)
    return [
        {
            "id": str(t.id),
            "transaction_ref": t.transaction_ref,
            "amount": t.amount,
            "merchant": t.merchant,
            "category": t.category,
            "country": t.country,
            "fraud_score": t.fraud_score,
            "risk_level": t.risk_level.value if t.risk_level else None,
            "is_fraud": t.is_fraud,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
        }
        for t in txns
    ]
