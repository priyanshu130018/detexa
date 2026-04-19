"""
api/main.py
─────────────────────────────────────────────────────────────────────────────
FastAPI application factory.  Run with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import auth, predict, alerts as alerts_router
from core.config import settings
from core.logging import logger
from database.db import engine
from database.models import Base


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀  Starting {settings.app_name} v{settings.app_version}")
    # Auto-create tables (use Alembic for production migrations)
    Base.metadata.create_all(bind=engine)
    # Pre-load ML models
    from ml.models.credit_fraud_model import CreditFraudModel
    from ml.models.behavior_model import BehaviorAnomalyModel
    CreditFraudModel.get_instance()
    BehaviorAnomalyModel.get_instance()
    yield
    logger.info("Shutting down …")


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="Production-grade fraud detection API",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
PREFIX = "/api/v1"
app.include_router(auth.router,           prefix=PREFIX)
app.include_router(predict.router,        prefix=PREFIX)
app.include_router(alerts_router.router,  prefix=PREFIX)


# ── Health-check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "app": settings.app_name, "version": settings.app_version}


@app.get("/", tags=["System"])
def root():
    return JSONResponse({"message": f"Welcome to {settings.app_name} API", "docs": "/docs"})
