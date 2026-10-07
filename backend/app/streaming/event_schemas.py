"""
app/streaming/event_schemas.py
─────────────────────────────────────────────────────────────────────────────
Reusable Pydantic v2 schemas for real-time Kafka & Flink event streaming.
Ensures strict idempotency, versioning, and end-to-end type safety for Indian Banking Transactions.
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
    version: str = Field(default="2.0.0", description="Event payload schema semantic version")
    partition_key: Optional[str] = Field(
        None, description="Kafka partition routing key (e.g. customer_id or user_id)"
    )


class TransactionPayload(BaseModel):
    transaction_ref: str = Field(..., description="Unique business reference string")
    customer_id: Optional[str] = Field(None, description="Account holder Customer ID (e.g. CUST003688)")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    amount: float = Field(..., gt=0, description="Monetary transaction amount in INR")
    transaction_amount: Optional[float] = Field(None, description="Transaction amount in INR")
    currency: str = Field(default="INR", max_length=10, description="ISO currency code")
    merchant: str = Field(default="Online Merchant", max_length=150)
    category: str = Field(default="Retail", max_length=60)
    merchant_category: str = Field(default="Retail", max_length=60)
    country: str = Field(default="IN", max_length=60)
    device_fingerprint: Optional[str] = Field(None, description="Client hardware/browser fingerprint")
    user_agent: Optional[str] = None
    ip_address: Optional[str] = Field(None, description="Client IPv4/IPv6 address")

    # Indian Banking Transaction Fields
    account_type: str = Field(default="Savings", description="Savings, Current, Salary, NRI, Fixed Deposit")
    transaction_type: str = Field(default="UPI", description="UPI, IMPS, NEFT, POS, ATM_Withdrawal, Net_Banking, RTGS, etc.")
    transaction_direction: str = Field(default="Debit", description="Debit or Credit")
    account_balance: float = Field(default=50000.0, description="Current account balance in INR")
    state: str = Field(default="Maharashtra", description="Indian State")
    credit_score: int = Field(default=650, description="Credit score [300-900]")
    has_loan: int = Field(default=0, description="1 if loan exists else 0")
    loan_type: str = Field(default="None", description="Loan type")
    emi_amount: float = Field(default=0.0, description="Monthly EMI in INR")
    transaction_status: str = Field(default="Success", description="Success, Failed, Reversed, Pending")
    channel: str = Field(default="Mobile_App", description="Mobile_App, Web, ATM, POS_Terminal, Branch, API")
    kyc_status: str = Field(default="Verified", description="Verified, Pending, Expired")
    transaction_hour: int = Field(default=12, description="Hour of transaction (0-23)")
    transaction_date: Optional[str] = Field(None, description="Transaction date (YYYY-MM-DD)")
    transaction_time: Optional[str] = Field(None, description="Transaction time (HH:MM)")


class AggregatedFeatures(BaseModel):
    """
    Real-time stateful streaming features computed over tumbling and sliding Flink windows.
    """
    velocity_1m: int = Field(default=1, description="Transaction count for customer in last 1 minute")
    velocity_5m: int = Field(default=1, description="Transaction count for customer in last 5 minutes")
    velocity_1h: int = Field(default=1, description="Transaction count for customer in last 1 hour")
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
    """Event produced by Flink engine to 'detexa.transactions.scored' topic."""
    header: EventHeader
    payload: TransactionPayload
    streaming_features: AggregatedFeatures
    fraud_score: float
    risk_level: str
    decision: str
    reason_codes: List[str]
    shap_top_features: Optional[List[Dict[str, Any]]] = None
    latency_ms: float
    model_version: str


class FraudAlertEvent(BaseModel):
    """High-priority incident alert event produced to 'detexa.alerts.high_risk' topic."""
    header: EventHeader
    alert_id: str
    transaction_id: str
    transaction_ref: str
    user_id: Optional[str] = None
    customer_id: Optional[str] = None
    score: float
    risk_level: str
    decision: str
    description: str
    reason_codes: List[str]
    shap_drivers: Optional[List[Dict[str, Any]]] = None


class DeadLetterEvent(BaseModel):
    header: EventHeader
    failed_topic: Optional[str] = None
    failed_payload: Optional[Dict[str, Any]] = None
    raw_payload: Optional[str] = None
    error_message: str
    retry_count: int = 0
