"""
database/models.py
─────────────────────────────────────────────────────────────────────────────
All SQLAlchemy ORM table definitions.

Tables
------
users           – registered users
transactions    – credit-card transactions (raw + enriched)
behavior_logs   – per-session behavioural signals
alerts          – high-risk events raised by the detection engine
prediction_logs – audit trail: every model inference call
"""

from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.db import Base


def _now():
    return datetime.now(timezone.utc)


# ── Enums ─────────────────────────────────────────────────────────────────────

class RiskLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# ── Tables ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    mobile = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    last_login = Column(DateTime(timezone=True), nullable=True)

    transactions = relationship("Transaction", back_populates="user", lazy="dynamic")
    behavior_logs = relationship("BehaviorLog", back_populates="user", lazy="dynamic")
    alerts = relationship("Alert", back_populates="user", lazy="dynamic")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    transaction_ref = Column(String(64), unique=True, index=True)

    # Raw card features (mirrors Kaggle creditcard.csv columns)
    amount = Column(Float, nullable=False)
    v1 = Column(Float); v2 = Column(Float); v3 = Column(Float)
    v4 = Column(Float); v5 = Column(Float); v6 = Column(Float)
    v7 = Column(Float); v8 = Column(Float); v9 = Column(Float)
    v10 = Column(Float); v11 = Column(Float); v12 = Column(Float)
    v13 = Column(Float); v14 = Column(Float); v15 = Column(Float)
    v16 = Column(Float); v17 = Column(Float); v18 = Column(Float)
    v19 = Column(Float); v20 = Column(Float); v21 = Column(Float)
    v22 = Column(Float); v23 = Column(Float); v24 = Column(Float)
    v25 = Column(Float); v26 = Column(Float); v27 = Column(Float)
    v28 = Column(Float)

    # Enriched / derived
    merchant = Column(String(120), nullable=True)
    category = Column(String(60), nullable=True)
    country = Column(String(60), nullable=True)
    currency = Column(String(10), default="USD")

    # Detection results
    fraud_score = Column(Float, nullable=True)
    risk_level = Column(Enum(RiskLevel), nullable=True)
    is_fraud = Column(Boolean, default=False)
    label = Column(Integer, nullable=True)          # ground-truth (0/1)

    timestamp = Column(DateTime(timezone=True), default=_now, index=True)

    user = relationship("User", back_populates="transactions")
    alert = relationship("Alert", back_populates="transaction", uselist=False)


class BehaviorLog(Base):
    __tablename__ = "behavior_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id = Column(String(64), index=True)

    ip_address = Column(String(45))
    device_fingerprint = Column(String(255))
    user_agent = Column(Text)
    login_hour = Column(Integer)                    # 0-23
    typing_speed = Column(Float)                    # chars/sec
    mouse_velocity = Column(Float)
    geo_country = Column(String(60))
    geo_city = Column(String(60))
    is_vpn = Column(Boolean, default=False)
    is_tor = Column(Boolean, default=False)
    failed_logins = Column(Integer, default=0)
    device_change = Column(Boolean, default=False)

    anomaly_score = Column(Float, nullable=True)
    risk_level = Column(Enum(RiskLevel), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, index=True)

    user = relationship("User", back_populates="behavior_logs")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)

    alert_type = Column(String(60))                 # "credit_fraud" | "behavior_anomaly"
    risk_level = Column(Enum(RiskLevel), nullable=False)
    score = Column(Float)
    description = Column(Text)
    status = Column(Enum(AlertStatus), default=AlertStatus.OPEN)
    shap_values = Column(JSON, nullable=True)       # feature importance payload
    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="alerts")
    transaction = relationship("Transaction", back_populates="alert")


class PredictionLog(Base):
    __tablename__ = "prediction_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint = Column(String(60))
    input_hash = Column(String(64))
    fraud_score = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    risk_level = Column(Enum(RiskLevel), nullable=True)
    latency_ms = Column(Float)
    model_version = Column(String(30))
    created_at = Column(DateTime(timezone=True), default=_now)
