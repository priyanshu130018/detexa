"""
api/routers/predict.py
─────────────────────────────────────────────────────────────────────────────
POST /predict/credit    – credit-card fraud score
POST /predict/behavior  – behavioural anomaly score
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.middleware.auth_middleware import get_current_user
from database.db import get_db
from database.models import User
from models.schemas import (
    BehaviorIn, BehaviorPredictionOut,
    TransactionIn, FraudPredictionOut,
)
from services.behavior_service import BehaviorDetectionService
from services.fraud_service import FraudDetectionService

router = APIRouter(prefix="/predict", tags=["Prediction"])


@router.post("/credit", response_model=FraudPredictionOut)
def predict_credit(
    payload: TransactionIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run the credit-card fraud model and return a risk score."""
    svc = FraudDetectionService(db)
    return svc.predict_credit(payload.model_dump())


@router.post("/behavior", response_model=BehaviorPredictionOut)
def predict_behavior(
    payload: BehaviorIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Run the behavioural anomaly detector and return an anomaly score."""
    svc = BehaviorDetectionService(db)
    return svc.predict_behavior(payload.model_dump())
