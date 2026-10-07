"""
app/db/base.py
─────────────────────────────────────────────────────────────────────────────
Aggregate Base and all normalized ORM models for Alembic discovery and app imports.
"""

from app.db.session import Base
from app.db.models import (
    # Core Models
    User,
    Merchant,
    Device,
    IPAddress,
    Transaction,
    ModelMetadata,
    FraudPrediction,
    FraudAlert,
    BehaviorLog,
    AuditLog,
    # Enums
    RiskLevel,
    AlertStatus,
    DecisionType,
    # Backward compatibility aliases
    Alert,
    PredictionLog,
    # Custom Types
    GUID,
    JSONType,
)

__all__ = [
    "Base",
    "User",
    "Merchant",
    "Device",
    "IPAddress",
    "Transaction",
    "ModelMetadata",
    "FraudPrediction",
    "FraudAlert",
    "BehaviorLog",
    "AuditLog",
    "RiskLevel",
    "AlertStatus",
    "DecisionType",
    "Alert",
    "PredictionLog",
    "GUID",
    "JSONType",
]
