"""
flink/models/state_schemas.py
─────────────────────────────────────────────────────────────────────────────
Data models and state structures for PyFlink stateful stream processing.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class TransactionRecord:
    timestamp: float
    amount: float
    merchant: str
    category: str
    country: str
    device_fingerprint: Optional[str]
    ip_address: Optional[str]
    is_failed: bool = False


@dataclass
class WindowMetrics:
    """
    Extracted streaming window features for ML inference and rule evaluation.
    """
    # 1. Velocity & Count Features
    velocity_1m: int = 1
    velocity_5m: int = 1
    velocity_15m: int = 1
    velocity_1h: int = 1
    velocity_24h: int = 1

    # 2. Monetary Features
    rolling_amount_1h: float = 0.0
    avg_amount_1h: float = 0.0
    max_amount_1h: float = 0.0
    rolling_amount_24h: float = 0.0
    avg_amount_24h: float = 0.0
    amount_deviation_ratio: float = 1.0  # current amount / avg_amount_1h

    # 3. Failed Transaction Tracking
    failed_txn_count_5m: int = 0
    failed_txn_count_1h: int = 0

    # 4. Behavioral & Device State
    distinct_devices_15m: int = 1
    device_changed: bool = False
    distinct_ips_15m: int = 1
    ip_changed: bool = False
    distinct_merchants_1h: int = 1
    distinct_categories_1h: int = 1

    # 5. Unusual Timing Metrics
    is_unusual_hour: bool = False  # Diurnal off-peak hours (02:00 - 05:00)
    hour_of_day: float = 12.0
    sin_hour: float = 0.0
    cos_hour: float = 0.0
    seconds_since_last_txn: float = 0.0


@dataclass
class UserStreamState:
    """
    State stored in Flink Keyed State (ValueState / ListState) per user/card.
    """
    user_key: str
    total_txns_seen: int = 0
    first_seen_ts: float = 0.0
    last_seen_ts: float = 0.0
    recent_transactions: List[Dict[str, Any]] = field(default_factory=list)
    recent_devices: List[str] = field(default_factory=list)
    recent_ips: List[str] = field(default_factory=list)
    recent_countries: List[str] = field(default_factory=list)
    failed_attempts: List[float] = field(default_factory=list)


@dataclass
class FlinkEnrichedEvent:
    """
    Enriched event ready for fraud scoring and decisioning.
    """
    event_id: str
    idempotency_key: str
    transaction_ref: str
    user_id: Optional[str]
    amount: float
    currency: str
    merchant: str
    category: str
    country: str
    device_fingerprint: Optional[str]
    ip_address: Optional[str]
    pca_features: Dict[str, float]
    window_metrics: WindowMetrics
    ingestion_ts: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
