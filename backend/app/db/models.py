"""
app/db/models.py
─────────────────────────────────────────────────────────────────────────────
Normalized SQLAlchemy 2.0 ORM schema optimized for PostgreSQL / Neon Serverless.

Entities:
- User (Identity & Authentication)
- Merchant (Normalized Merchant directory & risk tracking)
- Device (Device fingerprints, user agents, trust scores)
- IPAddress (IP reputation, geo-location, VPN/TOR flags)
- Transaction (Credit card transaction records with PCA features)
- ModelMetadata (ML model registry and version registry)
- FraudPrediction (Decision records, inference audits, SHAP values)
- FraudAlert (Security incident triage and status lifecycle)
- BehaviorLog (Granular behavioral telemetry)
- AuditLog (System-wide security and modification audit trail)
"""

from datetime import datetime, timezone
import enum
import uuid

from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, Enum, Float,
    ForeignKey, Index, Integer, String, Text, UniqueConstraint, JSON,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import CHAR, TypeDecorator

from app.db.session import Base


def _now():
    return datetime.now(timezone.utc)


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's native UUID type on Postgres/Neon, CHAR(36) on SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class JSONType(TypeDecorator):
    """Platform-independent JSON type.
    Uses JSONB on PostgreSQL, standard JSON elsewhere.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB)
        else:
            return dialect.type_descriptor(JSON)


# ── Enumerations ─────────────────────────────────────────────────────────────

class RiskLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class DecisionType(str, enum.Enum):
    ALLOW = "ALLOW"
    CHALLENGE = "CHALLENGE"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"



# ── 1. Users Table ───────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    mobile = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    devices = relationship("Device", back_populates="user")
    alerts = relationship("FraudAlert", foreign_keys="FraudAlert.user_id", back_populates="user")
    assigned_alerts = relationship("FraudAlert", foreign_keys="FraudAlert.assigned_to", back_populates="assignee")
    behavior_logs = relationship("BehaviorLog", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")


# ── 2. Merchants Table ───────────────────────────────────────────────────────

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False, index=True)
    category = Column(String(60), nullable=False, index=True)
    risk_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    transactions = relationship("Transaction", back_populates="merchant_rel")


# ── 3. Devices Table ─────────────────────────────────────────────────────────

class Device(Base):
    __tablename__ = "devices"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_fingerprint = Column(String(255), nullable=False, index=True)
    user_agent = Column(Text, nullable=True)
    is_trusted = Column(Boolean, nullable=False, default=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    user = relationship("User", back_populates="devices")
    transactions = relationship("Transaction", back_populates="device")
    behavior_logs = relationship("BehaviorLog", back_populates="device")

    __table_args__ = (
        UniqueConstraint("user_id", "device_fingerprint", name="uq_user_device_fingerprint"),
    )


# ── 4. IP Addresses Table ────────────────────────────────────────────────────

class IPAddress(Base):
    __tablename__ = "ip_addresses"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    geo_country = Column(String(60), nullable=True, index=True)
    geo_city = Column(String(60), nullable=True)
    is_vpn = Column(Boolean, nullable=False, default=False)
    is_tor = Column(Boolean, nullable=False, default=False)
    reputation_score = Column(Float, nullable=False, default=0.0)
    last_checked_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    transactions = relationship("Transaction", back_populates="ip_rel")
    behavior_logs = relationship("BehaviorLog", back_populates="ip_rel")


# ── 5. Transactions Table ────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    customer_id = Column(String(64), nullable=True, index=True)
    merchant_id = Column(GUID(), ForeignKey("merchants.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(GUID(), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_id = Column(GUID(), ForeignKey("ip_addresses.id", ondelete="SET NULL"), nullable=True, index=True)

    transaction_ref = Column(String(64), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    transaction_amount = Column(Float, nullable=True)
    currency = Column(String(10), nullable=False, default="INR")
    merchant = Column(String(120), nullable=True)
    category = Column(String(60), nullable=True)
    country = Column(String(60), nullable=True, default="IN")

    # Indian Banking Transaction Attributes
    account_type = Column(String(30), nullable=True)
    transaction_type = Column(String(30), nullable=True)
    transaction_direction = Column(String(10), nullable=True)
    account_balance = Column(Float, nullable=True)
    merchant_category = Column(String(60), nullable=True)
    state = Column(String(40), nullable=True)
    credit_score = Column(Integer, nullable=True)
    has_loan = Column(Integer, nullable=True)
    loan_type = Column(String(30), nullable=True)
    emi_amount = Column(Float, nullable=True)
    transaction_status = Column(String(30), nullable=True)
    channel = Column(String(30), nullable=True)
    kyc_status = Column(String(30), nullable=True)
    transaction_hour = Column(Integer, nullable=True)
    transaction_date = Column(String(10), nullable=True)
    transaction_time = Column(String(8), nullable=True)

    # Detection outputs denormalized for query acceleration
    fraud_score = Column(Float, nullable=True)
    risk_level = Column(Enum(RiskLevel), nullable=True, index=True)
    is_fraud = Column(Boolean, nullable=False, default=False, index=True)
    label = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    # Relationships
    user = relationship("User", back_populates="transactions")
    merchant_rel = relationship("Merchant", back_populates="transactions")
    device = relationship("Device", back_populates="transactions")
    ip_rel = relationship("IPAddress", back_populates="transactions")
    prediction = relationship("FraudPrediction", back_populates="transaction", uselist=False)
    alert = relationship("FraudAlert", back_populates="transaction", uselist=False)

    __table_args__ = (
        CheckConstraint("amount > 0", name="chk_positive_transaction_amount"),
        Index("ix_transactions_user_timestamp", "user_id", "timestamp"),
        Index("ix_transactions_fraud_timestamp", "is_fraud", "timestamp"),
    )


# ── 6. Model Metadata Registry ───────────────────────────────────────────────

class ModelMetadata(Base):
    __tablename__ = "model_metadata"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    model_name = Column(String(100), nullable=False, index=True)
    version = Column(String(30), nullable=False)
    algorithm = Column(String(60), nullable=False)
    threshold = Column(Float, nullable=False, default=0.50)
    is_active = Column(Boolean, nullable=False, default=True)
    metrics = Column(JSONType(), nullable=True)
    trained_at = Column(DateTime(timezone=True), nullable=False, default=_now)

    predictions = relationship("FraudPrediction", back_populates="model", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_name_version"),
    )


# ── 7. Fraud Predictions Table ───────────────────────────────────────────────

class FraudPrediction(Base):
    __tablename__ = "fraud_predictions"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(GUID(), ForeignKey("transactions.id", ondelete="CASCADE"), unique=True, nullable=True, index=True)
    model_id = Column(GUID(), ForeignKey("model_metadata.id", ondelete="SET NULL"), nullable=True, index=True)

    endpoint = Column(String(60), nullable=False)
    input_hash = Column(String(64), nullable=True, index=True)
    fraud_score = Column(Float, nullable=False)
    anomaly_score = Column(Float, nullable=True)
    risk_level = Column(Enum(RiskLevel), nullable=False, index=True)
    is_fraud = Column(Boolean, nullable=False, default=False)
    decision = Column(Enum(DecisionType), nullable=False, default=DecisionType.ALLOW)
    shap_values = Column(JSONType(), nullable=True)
    latency_ms = Column(Float, nullable=False)
    model_version = Column(String(30), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    transaction = relationship("Transaction", back_populates="prediction")
    model = relationship("ModelMetadata", back_populates="predictions")
    alert = relationship("FraudAlert", back_populates="prediction", uselist=False)

    __table_args__ = (
        CheckConstraint("fraud_score >= 0.0 AND fraud_score <= 1.0", name="chk_fraud_score_range"),
    )


# ── 8. Fraud Alerts Table ────────────────────────────────────────────────────

class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    transaction_id = Column(GUID(), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    prediction_id = Column(GUID(), ForeignKey("fraud_predictions.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_to = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    alert_type = Column(String(60), nullable=False)   # "credit_fraud" | "behavior_anomaly"
    risk_level = Column(Enum(RiskLevel), nullable=False, index=True)
    score = Column(Float, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.OPEN, index=True)
    resolution_notes = Column(Text, nullable=True)
    shap_values = Column(JSONType(), nullable=True)
    metadata_ = Column("metadata", JSONType(), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="alerts")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_alerts")
    transaction = relationship("Transaction", back_populates="alert")
    prediction = relationship("FraudPrediction", back_populates="alert")

    __table_args__ = (
        Index("ix_fraud_alerts_status_risk_created", "status", "risk_level", "created_at"),
    )


# ── 9. Behavior Logs Table ───────────────────────────────────────────────────

class BehaviorLog(Base):
    __tablename__ = "behavior_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id = Column(GUID(), ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_id = Column(GUID(), ForeignKey("ip_addresses.id", ondelete="SET NULL"), nullable=True, index=True)

    session_id = Column(String(64), nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    device_fingerprint = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    login_hour = Column(Integer, nullable=True)
    typing_speed = Column(Float, nullable=True)
    mouse_velocity = Column(Float, nullable=True)
    geo_country = Column(String(60), nullable=True)
    geo_city = Column(String(60), nullable=True)
    is_vpn = Column(Boolean, nullable=False, default=False)
    is_tor = Column(Boolean, nullable=False, default=False)
    failed_logins = Column(Integer, nullable=False, default=0)
    device_change = Column(Boolean, nullable=False, default=False)

    anomaly_score = Column(Float, nullable=True, index=True)
    risk_level = Column(Enum(RiskLevel), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="behavior_logs")
    device = relationship("Device", back_populates="behavior_logs")
    ip_rel = relationship("IPAddress", back_populates="behavior_logs")


# ── 10. Audit Logs Table ─────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True, index=True)
    entity_id = Column(String(64), nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSONType(), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now, index=True)

    user = relationship("User", back_populates="audit_logs")


# Legacy alias compatibility
Alert = FraudAlert
PredictionLog = FraudPrediction
