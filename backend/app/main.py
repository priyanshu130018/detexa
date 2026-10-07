"""
app/main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application factory, OpenAPI configuration, and lifecycle handlers.
"""

from contextlib import asynccontextmanager
from datetime import datetime
import warnings

try:
    from sklearn.exceptions import InconsistentVersionWarning
    warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
except Exception:
    pass
warnings.filterwarnings("ignore", message=".*unpickle estimator.*")
warnings.filterwarnings("ignore", message=r".*serialized model.*")
warnings.filterwarnings("ignore", message=r".*error_msg\.h.*")
warnings.filterwarnings("ignore", message=r".*Booster\.save_model.*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"xgboost(\..*)?")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, apply_security_log_filters
from app.core.redis import get_redis_client
from app.db.base import Base
from app.db.session import engine
from app.models.schemas import HealthResponse, ReadinessResponse

# OpenAPI Tag Metadata
OPENAPI_TAGS = [
    {
        "name": "Authentication & Users",
        "description": "User registration, authentication with JWT, and account management.",
    },
    {
        "name": "Transactions",
        "description": "Search, filter, paginate, and inspect normalized transaction details.",
    },
    {
        "name": "AI Prediction & Risk Scoring",
        "description": "Real-time single/batch credit card fraud and session behavioral anomaly inference.",
    },
    {
        "name": "Alerts & Incident Triage",
        "description": "Security incident lifecycle, triage assignments, and investigation resolution.",
    },
    {
        "name": "Decisions & AI Governance",
        "description": "Inference decision logs, automated verdicts (ALLOW/REVIEW/BLOCK), and analyst manual overrides.",
    },
    {
        "name": "Dashboard Analytics",
        "description": "High-level KPIs, time-series volume trends, risk tiers, and category/geo threat mapping.",
    },
    {
        "name": "Behavioral Analytics",
        "description": "Telemetry logs for user typing speed, mouse velocity, device consistency, and proxy indicators.",
    },
    {
        "name": "System Health & Model Registry",
        "description": "Liveness probes, readiness diagnostics, and registered ML model metadata.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_security_log_filters()
    logger.info(f"Starting {settings.app_name} v{settings.app_version} [{settings.app_env}]")

    # In production, schema is managed strictly via Alembic migrations (alembic upgrade head).
    if settings.app_env in ["development", "testing", "test"] and not settings.database_url.startswith("postgresql"):
        Base.metadata.create_all(bind=engine)
        logger.info("Dev SQLite tables verified.")
    elif settings.app_env == "production":
        logger.info("Production mode: schema managed via Alembic migrations.")
    else:
        logger.info("Database schema management active.")

    # Pre-load singleton ML models
    try:
        from app.ml.models.banking_fraud_model import BankingFraudModel
        from app.ml.models.behavior_model import BehaviorAnomalyModel
        BankingFraudModel.get_instance()
        BehaviorAnomalyModel.get_instance()
    except Exception as exc:
        logger.warning(f"Could not pre-load ML models on startup: {exc}")

    # Initialize Redis connection pool
    if settings.redis_enabled:
        get_redis_client()

    # Initialize Realtime Broadcaster Event Loop
    try:
        import asyncio
        from app.core.realtime_broadcaster import get_realtime_broadcaster
        get_realtime_broadcaster().set_event_loop(asyncio.get_running_loop())
    except Exception as exc:
        logger.warning(f"Could not bind realtime broadcaster event loop: {exc}")

    yield

    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=f"{settings.app_name} API",
    description="""
# Detexa Financial Fraud Detection & Behavioral Analytics Platform API

Detexa provides enterprise-grade AI fraud prevention, automated transaction decisions (`ALLOW`, `REVIEW`, `BLOCK`), SHAP-driven explainability, session behavioral anomaly tracking, and incident triage.

### Features:
* **Versioned REST API**: Standardized under `/api/v1`
* **Real-time AI Scoring**: Sub-50ms ensemble ML inference
* **Explainable AI**: Top SHAP feature drivers for every prediction
* **Incident Triage Workflow**: Status management, analyst assignment, and resolution audit trail
* **AI Governance & Overrides**: Manual analyst override capability with audit justification
* **Centralized Configuration & Caching**: Redis-backed statistics and low-latency prediction caching
    """,
    version=settings.app_version,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_v1_str}/openapi.json",
    lifespan=lifespan,
)

# ── Register Global Unified Exception Handlers ──────────────────────────────
register_exception_handlers(app)

# ── CORS Middleware ──────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if isinstance(settings.cors_origins, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Versioned Routers ──────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.api_v1_str)


# ── Root & System Probes ─────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System Health & Model Registry"])
def health() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(
        status="healthy",
        app=settings.app_name,
        version=settings.app_version,
        env=settings.app_env,
        timestamp=datetime.utcnow(),
    )


@app.get("/health/ready", response_model=ReadinessResponse, tags=["System Health & Model Registry"])
def readiness() -> ReadinessResponse:
    """Readiness probe checking DB and Redis connectivity."""
    db_ok = True
    redis_ok = True
    models_ok = True

    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as e:
        db_ok = False
        logger.error(f"Database readiness check failed: {e}")

    try:
        r = get_redis_client()
        if r:
            r.ping()
    except Exception:
        redis_ok = False

    try:
        from app.ml.models.banking_fraud_model import BankingFraudModel
        from app.ml.models.behavior_model import BehaviorAnomalyModel
        m1 = BankingFraudModel.get_instance()
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


@app.get("/", tags=["System Health & Model Registry"])
def root():
    return JSONResponse({
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "api_v1": settings.api_v1_str,
    })
