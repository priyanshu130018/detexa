"""
models/schemas.py
─────────────────────────────────────────────────────────────────────────────
Pydantic v2 request / response schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    mobile: Optional[str] = Field(None, pattern=r"^\+?[0-9\s\-]{7,20}$")
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    email: str


class UserOut(BaseModel):
    id: UUID
    name: str
    email: str
    mobile: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Transaction / Credit Fraud ────────────────────────────────────────────────

class TransactionIn(BaseModel):
    """Raw features for the credit-card fraud model (mirrors Kaggle dataset)."""
    amount: float = Field(..., gt=0)
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

    # Optional enrichment
    merchant: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None
    user_id: Optional[str] = None


class FraudPredictionOut(BaseModel):
    transaction_id: str
    fraud_score: float
    risk_level: str
    is_fraud: bool
    shap_top_features: Optional[List[Dict[str, Any]]] = None
    model_version: str
    latency_ms: float


# ── Behavior Fraud ────────────────────────────────────────────────────────────

class BehaviorIn(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    ip_address: str = "0.0.0.0"
    device_fingerprint: str = ""
    user_agent: str = ""
    login_hour: int = Field(0, ge=0, le=23)
    typing_speed: float = Field(0.0, ge=0)
    mouse_velocity: float = Field(0.0, ge=0)
    geo_country: str = ""
    geo_city: str = ""
    is_vpn: bool = False
    is_tor: bool = False
    failed_logins: int = Field(0, ge=0)
    device_change: bool = False


class BehaviorPredictionOut(BaseModel):
    session_id: str
    anomaly_score: float
    risk_level: str
    is_anomalous: bool
    latency_ms: float


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: UUID
    alert_type: str
    risk_level: str
    score: float
    description: str
    status: str
    created_at: datetime
    transaction_id: Optional[UUID]
    user_id: Optional[UUID]

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    status: str


# ── Dashboard Stats ───────────────────────────────────────────────────────────

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
