"""
app/api/v1/endpoints/__init__.py
─────────────────────────────────────────────────────────────────────────────
Endpoint modules export.
"""

from app.api.v1.endpoints import (
    alerts,
    auth,
    behavior,
    dashboard,
    decisions,
    feature_store,
    graph,
    predict,
    streaming,
    system,
    transactions,
)

__all__ = [
    "alerts",
    "auth",
    "behavior",
    "dashboard",
    "decisions",
    "feature_store",
    "graph",
    "predict",
    "streaming",
    "system",
    "transactions",
]
