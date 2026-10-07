"""
app/api/v1/api.py
─────────────────────────────────────────────────────────────────────────────
Aggregate version 1 API router mounting all modular domain endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    alerts,
    auth,
    behavior,
    dashboard,
    decisions,
    feature_store,
    graph,
    predict,
    realtime,
    streaming,
    system,
    transactions,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(transactions.router)
api_router.include_router(streaming.router)
api_router.include_router(realtime.router)
api_router.include_router(feature_store.router, prefix="/features", tags=["Feature Store"])
api_router.include_router(graph.router, prefix="/graph", tags=["Graph Analytics"])
api_router.include_router(predict.router)
api_router.include_router(alerts.router)
api_router.include_router(decisions.router)
api_router.include_router(dashboard.router)
api_router.include_router(behavior.router)
api_router.include_router(system.router)


