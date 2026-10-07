"""
app/streaming/event_schemas.py
─────────────────────────────────────────────────────────────────────────────
Reusable Pydantic v2 schemas for real-time Kafka & Flink event streaming.
Ensures strict idempotency, versioning, and end-to-end type safety.
"""

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventType(str, enum.Enum):
    TRANSACTION_INGESTED = "TRANSACTION_INGESTED"
    TRANSACTION_SCORED = "TRANSACTION_SCORED"
    ALERT_GENERATED = "ALERT_GENERATED"
    DECISION_COMMITTED = "DECISION_COMMITTED"
    DEAD_LETTER = "DEAD_LETTER"


class EventHeader(BaseModel):
    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique globally unique identifier for this message event",
    )
    idempotency_key: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Deterministic idempotency token ensuring exactly-once processing semantics",
    )
    event_type: EventType = Field(..., description="Categorical event topic identifier")
    timestamp: str = Field(default_factory=_utc_now_iso, description="ISO-8601 UTC timestamp")
    source: str = Field(default="detexa-transaction-api", description="Originating service or gateway")
    version: str = Field(default="1.0.0", description="Event payload schema semantic version")
    partition_key: Optional[str] = Field(
        None, description="Kafka partition routing key (e.g. user_id or card_hash)"
    )


class TransactionPayload(BaseModel):
    transaction_ref: str = Field(..., description="Unique business reference string")
    amount: float = Field(..., gt=0, description="Monetary transaction amount")
    currency: str = Field(default="USD", max_length=10, description="ISO currency code")
    merchant: str = Field(default="Online Merchant", max_length=150)
    category: str = Field(default="General", max_length=60)
    country: str = Field(default="US", max_length=60)
    user_id: Optional[str] = Field(None, description="Account holder UUID")
    device_fingerprint: Optional[str] = Field(None, description="Client hardware/browser fingerprint")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = Field(None, description="Client IPv4/IPv6 address")

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


class AggregatedFeatures(BaseModel):
    """
    Real-time stateful streaming features computed over tumbling and sliding Flink windows.
    """
    velocity_1m: int = Field(default=1, description="Transaction count for card in last 1 minute")
    velocity_5m: int = Field(default=1, description="Transaction count for card in last 5 minutes")
    velocity_1h: int = Field(default=1, description="Transaction count for card in last 1 hour")
    rolling_amount_1h: float = Field(default=0.0, description="Cumulative transaction amount in last 1 hour")
    avg_amount_1h: float = Field(default=0.0, description="Average transaction amount in last 1 hour")
    amount_deviation_ratio: float = Field(
        default=1.0, description="Ratio of current amount to 1-hour moving average"
    )
    distinct_merchants_1h: int = Field(default=1, description="Distinct merchants visited in last 1 hour")
    is_foreign_transaction: bool = Field(default=False, description="Flag indicating cross-border location mismatch")
    is_new_device: bool = Field(default=False, description="Flag indicating unrecognized hardware fingerprint")


class TransactionIngestionEvent(BaseModel):
    """Event produced by Transaction API to Kafka topic 'detexa.transactions.raw'."""
    header: EventHeader
    payload: TransactionPayload


class ScoredTransactionEvent(BaseModel):
    """Event emitted by Flink processor after ML scoring and decision engine evaluation."""
    header: EventHeader
    payload: TransactionPayload
    streaming_features: AggregatedFeatures
    fraud_score: float = Field(..., ge=0.0, le=1.0, description="Model fraud probability")
    risk_level: str = Field(..., description="Low, Medium, or High")
    decision: str = Field(..., description="ALLOW, REVIEW, or BLOCK")
    reason_codes: List[str] = Field(default_factory=list, description="Triggered rule and policy reason codes")
    shap_top_features: Optional[List[Dict[str, Any]]] = None
    latency_ms: float
    model_version: str


class FraudAlertEvent(BaseModel):
    """High-priority alert event published to 'detexa.alerts.high_risk' topic."""
    header: EventHeader
    alert_id: str
    transaction_id: str
    transaction_ref: str
    user_id: Optional[str] = None
    score: float
    risk_level: str
    decision: str
    description: str
    reason_codes: List[str]
    shap_drivers: Optional[List[Dict[str, Any]]] = None
    timestamp: str = Field(default_factory=_utc_now_iso)


class DeadLetterEvent(BaseModel):
    """Dead-letter queue envelope for unparseable or poisoned messages."""
    header: EventHeader
    failed_topic: str
    raw_payload: str
    error_message: str
    retry_count: int = 0
    captured_at: str = Field(default_factory=_utc_now_iso)
