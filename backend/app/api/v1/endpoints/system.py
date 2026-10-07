"""
app/api/v1/endpoints/system.py
─────────────────────────────────────────────────────────────────────────────
System health, readiness, and ML model registry REST API endpoints.
"""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.db.models import User
from app.db.session import engine
from app.models.schemas import HealthResponse, ModelMetadataOut, ReadinessResponse
from app.repositories.model_repo import ModelMetadataRepository

router = APIRouter(prefix="/system", tags=["System Health & Model Registry"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness Probe",
    description="Check whether the application process is running and responsive.",
)
def liveness_probe() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        timestamp=datetime.utcnow(),
    )


@router.get(
    "/readiness",
    response_model=ReadinessResponse,
    summary="Readiness Probe",
    description="Verify database connectivity, Redis cache availability, and loaded ML model status.",
)
def readiness_probe() -> ReadinessResponse:
    db_ok = True
    redis_ok = True
    models_ok = True

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        db_ok = False
        logger.error(f"Database readiness probe failed: {e}")

    try:
        r = get_redis_client()
        if r:
            r.ping()
    except Exception:
        redis_ok = False

    try:
        from app.ml.models.credit_fraud_model import CreditFraudModel
        from app.ml.models.behavior_model import BehaviorAnomalyModel
        m1 = CreditFraudModel.get_instance()
        m2 = BehaviorAnomalyModel.get_instance()
        models_ok = m1 is not None and m2 is not None
    except Exception:
        models_ok = False

    overall_status = "ready" if (db_ok and models_ok) else "degraded"
    return ReadinessResponse(
        status=overall_status,
        database="connected" if db_ok else "disconnected",
        redis="connected" if (redis_ok and settings.redis_enabled) else "disabled/unreachable",
        models_loaded=models_ok,
        timestamp=datetime.utcnow(),
    )


@router.get(
    "/models",
    response_model=List[ModelMetadataOut],
    summary="List Active ML Models",
    description="Retrieve registry metadata, active algorithms, thresholds, and performance metrics for all registered AI models.",
)
def list_models(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[ModelMetadataOut]:
    repo = ModelMetadataRepository(db)
    return repo.list_active()
