"""
app/models/schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic v2 validation schemas for Detexa REST API.
"""

from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

T = TypeVar("T")


# ── Generic Pagination Response ──────────────────────────────────────────────

class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int = Field(..., description="Total count of matching items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total available pages")
    has_next: bool = Field(..., description="Whether a next page exists")
    has_prev: bool = Field(..., description="Whether a previous page exists")


# ── Common Base Responses ───────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True


# ── Auth & User Schemas ─────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Full name")
    email: EmailStr = Field(..., description="Valid corporate or user email")
    mobile: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-]{7,20}$", description="E.164 or national phone")
    password: str = Field(..., min_length=8, description="Minimum 8 characters password")


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str
    is_admin: bool = False


class UserOut(BaseModel):
    id: UUID
    name: str
    email: str
    mobile: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserStatusUpdate(BaseModel):
    is_active: bool = Field(..., description="Set active or deactivated state")


# ── Normalized Entity Reference Schemas ─────────────────────────────────────

class MerchantOut(BaseModel):
    id: UUID
    name: str
    category: str
    risk_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class DeviceOut(BaseModel):
    id: UUID
    device_fingerprint: str
    user_agent: Optional[str] = None
    is_trusted: bool
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class IPAddressOut(BaseModel):
    id: UUID
    ip_address: str
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    is_vpn: bool
    is_tor: bool
    reputation_score: float

    model_config = {"from_attributes": True}


class ModelMetadataOut(BaseModel):
    id: UUID
    model_name: str
    version: str
    algorithm: str
    threshold: float
    is_active: bool
    metrics: Optional[Dict[str, Any]] = None
    trained_at: datetime

    model_config = {"from_attributes": True}


# ── Transaction Schemas ─────────────────────────────────────────────────────

class TransactionIn(BaseModel):
    amount: float = Field(..., gt=0, description="Transaction monetary amount (must be > 0)")
    currency: Optional[str] = Field("USD", max_length=10, description="ISO Currency code")
    merchant: Optional[str] = Field("Online Merchant", max_length=150, description="Merchant name")
    category: Optional[str] = Field("General", max_length=60, description="Merchant industry category")
    country: Optional[str] = Field("US", max_length=60, description="Country code")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    device_fingerprint: Optional[str] = Field(None, description="Client device fingerprint hash")
    user_agent: Optional[str] = Field(None, description="Client user agent string")
    ip_address: Optional[str] = Field(None, description="Client IP address")

    # Kaggle PCA Components V1–V28
    v1: float = 0.0;  v2: float = 0.0;  v3: float = 0.0
    v4: float = 0.0;  v5: float = 0.0;  v6: float = 0.0
    v7: float = 0.0;  v8: float = 0.0;  v9: float = 0.0
    v10: float = 0.0; v11: float = 0.0; v12: float = 0.0
    v13: float = 0.0; v14: float = 0.0; v15: float = 0.0
    v16: float = 0.0; v17: float = 0.0; v18: float = 0.0
    v19: float = 0.0; v20: float = 0.0; v21: float = 0.0
    v22: float = 0.0; v23: float = 0.0; v24: float = 0.0
    v25: float = 0.0; v26: float = 0.0; v27: float = 0.0
    v28: float = 0.0


class TransactionOut(BaseModel):
    id: UUID
    transaction_ref: str
    user_id: Optional[UUID] = None
    merchant_id: Optional[UUID] = None
    amount: float
    currency: str = "USD"
    merchant: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    fraud_score: Optional[float] = None
    risk_level: Optional[str] = None
    is_fraud: bool = False
    timestamp: datetime

    model_config = {"from_attributes": True}


class TransactionDetailOut(TransactionOut):
    device: Optional[DeviceOut] = None
    ip_rel: Optional[IPAddressOut] = None
    merchant_rel: Optional[MerchantOut] = None
    v1: Optional[float] = None; v2: Optional[float] = None; v3: Optional[float] = None
    v4: Optional[float] = None; v5: Optional[float] = None; v6: Optional[float] = None
    v7: Optional[float] = None; v8: Optional[float] = None; v9: Optional[float] = None
    v10: Optional[float] = None; v11: Optional[float] = None; v12: Optional[float] = None
    v13: Optional[float] = None; v14: Optional[float] = None; v15: Optional[float] = None
    v16: Optional[float] = None; v17: Optional[float] = None; v18: Optional[float] = None
    v19: Optional[float] = None; v20: Optional[float] = None; v21: Optional[float] = None
    v22: Optional[float] = None; v23: Optional[float] = None; v24: Optional[float] = None
    v25: Optional[float] = None; v26: Optional[float] = None; v27: Optional[float] = None
    v28: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Fraud Prediction Schemas ────────────────────────────────────────────────

class SHAPFeatureImpact(BaseModel):
    feature: str
    shap_value: float


class FraudPredictionOut(BaseModel):
    transaction_id: str
    transaction_ref: Optional[str] = None
    fraud_score: float = Field(..., ge=0.0, le=1.0, description="Predicted fraud probability (0.0 to 1.0)")
    risk_level: str = Field(..., description="Low, Medium, or High")
    decision: str = Field("ALLOW", description="Automated decision: ALLOW, REVIEW, or BLOCK")
    is_fraud: bool
    shap_top_features: Optional[List[Dict[str, Any]]] = Field(None, description="Top SHAP explainability drivers")
    model_version: str
    latency_ms: float

    model_config = {"from_attributes": True}


class BatchCreditFraudIn(BaseModel):
    transactions: List[TransactionIn] = Field(..., min_length=1, max_length=1000, description="List of transaction payloads")


class BatchCreditFraudOut(BaseModel):
    total_processed: int
    fraud_detected_count: int
    predictions: List[FraudPredictionOut]
    batch_latency_ms: float


# ── Decision Schemas ────────────────────────────────────────────────────────

class DecisionOut(BaseModel):
    id: UUID
    transaction_id: Optional[UUID] = None
    endpoint: str
    fraud_score: float
    risk_level: str
    decision: str
    is_fraud: bool
    latency_ms: float
    model_version: str
    created_at: datetime
    transaction: Optional[TransactionOut] = None

    model_config = {"from_attributes": True}


class DecisionOverrideRequest(BaseModel):
    new_decision: str = Field(..., description="Target override decision: ALLOW, CHALLENGE, REVIEW, or BLOCK")
    reason: str = Field(..., min_length=5, description="Analyst justification for overriding the AI decision")


class DecisionStatsOut(BaseModel):
    total_decisions: int
    allow_count: int
    challenge_count: int = 0
    review_count: int
    block_count: int
    allow_percentage: float
    challenge_percentage: float = 0.0
    review_percentage: float
    block_percentage: float



# ── Alert Schemas ────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: UUID
    alert_type: str
    risk_level: str
    score: float
    description: str
    status: str
    shap_values: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    created_at: datetime
    resolved_at: Optional[datetime] = None
    transaction_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    assigned_to: Optional[UUID] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AlertDetailOut(AlertOut):
    transaction: Optional[TransactionOut] = None
    user: Optional[UserOut] = None
    assignee: Optional[UserOut] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AlertStatusUpdate(BaseModel):
    status: str = Field(..., description="New triage status: open, reviewed, resolved, false_positive")


class AlertAssignRequest(BaseModel):
    assigned_to: UUID = Field(..., description="Target analyst User ID")


class AlertResolutionRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=5, description="Investigation findings and resolution rationale")
    status: str = Field("resolved", description="Status transition: resolved or false_positive")


# ── Behavioral Analytics Schemas ─────────────────────────────────────────────

class BehaviorIn(BaseModel):
    session_id: str = Field(..., description="Unique browser/device session identifier")
    user_id: Optional[str] = None
    ip_address: str = Field("0.0.0.0", description="Client IPv4 / IPv6 address")
    device_fingerprint: str = Field("", description="Client device hardware/browser fingerprint")
    user_agent: str = Field("", description="Browser user-agent string")
    login_hour: int = Field(12, ge=0, le=23, description="Hour of day (0-23)")
    typing_speed: float = Field(0.0, ge=0, description="Keystrokes per minute / cadence")
    mouse_velocity: float = Field(0.0, ge=0, description="Average mouse cursor speed in px/sec")
    geo_country: str = Field("US", description="Origin country code")
    geo_city: str = Field("Unknown", description="Origin city")
    is_vpn: bool = Field(False, description="VPN proxy indicator")
    is_tor: bool = Field(False, description="TOR exit node indicator")
    failed_logins: int = Field(0, ge=0, description="Consecutive failed password attempts")
    device_change: bool = Field(False, description="Whether device differs from historical profile")


class BehaviorPredictionOut(BaseModel):
    session_id: str
    anomaly_score: float
    risk_level: str
    is_anomalous: bool
    risk_factors: List[str] = []
    latency_ms: float


class BehaviorLogOut(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    session_id: str
    ip_address: Optional[str] = None
    device_fingerprint: Optional[str] = None
    user_agent: Optional[str] = None
    login_hour: Optional[int] = None
    typing_speed: Optional[float] = None
    mouse_velocity: Optional[float] = None
    geo_country: Optional[str] = None
    geo_city: Optional[str] = None
    is_vpn: bool = False
    is_tor: bool = False
    failed_logins: int = 0
    device_change: bool = False
    anomaly_score: Optional[float] = None
    risk_level: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BehaviorStatsOut(BaseModel):
    total_sessions: int
    high_risk_sessions: int
    medium_risk_sessions: int
    low_risk_sessions: int
    average_anomaly_score: float


# ── Dashboard Statistics Schemas ─────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_transactions: int
    fraud_count: int
    fraud_rate: float
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    total_alerts: int
    open_alerts: int
    avg_fraud_score: float
    cached: bool = False


class TimeSeriesPoint(BaseModel):
    date: str
    total_transactions: int
    fraud_transactions: int
    avg_score: float


class RiskDistribution(BaseModel):
    low: int
    medium: int
    high: int


class CategoryRiskBreakdown(BaseModel):
    category: str
    total_count: int
    fraud_count: int
    fraud_rate: float


class GeoRiskPoint(BaseModel):
    country: str
    transaction_count: int
    fraud_count: int
    risk_score: float


# ── System Health Schemas ────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    env: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str
    models_loaded: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
