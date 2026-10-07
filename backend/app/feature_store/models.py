"""
app/feature_store/models.py
─────────────────────────────────────────────────────────────────────────────
Data models and feature schemas stored in the Redis Real-Time Feature Store.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class VelocityFeatures:
    """Multi-scale rolling transaction count features."""
    velocity_1m: int = 1
    velocity_5m: int = 1
    velocity_15m: int = 1
    velocity_1h: int = 1
    velocity_24h: int = 1


@dataclass
class MonetaryFeatures:
    """Rolling window monetary statistics and deviation ratios."""
    rolling_amount_1h: float = 0.0
    avg_amount_1h: float = 0.0
    max_amount_1h: float = 0.0
    rolling_amount_24h: float = 0.0
    avg_amount_24h: float = 0.0
    amount_deviation_ratio: float = 1.0  # current_amount / max(avg_amount_1h, 10.0)


@dataclass
class MerchantFeatures:
    """Recent merchant diversity and category distribution."""
    recent_merchants_1h: List[str] = field(default_factory=list)
    distinct_merchants_1h: int = 1
    recent_categories_1h: List[str] = field(default_factory=list)
    distinct_categories_1h: int = 1


@dataclass
class DeviceFeatures:
    """Device fingerprint tracking and hardware switching flags."""
    recent_devices_15m: List[str] = field(default_factory=list)
    last_device: Optional[str] = None
    device_changed: bool = False
    distinct_devices_15m: int = 1


@dataclass
class IPFeatures:
    """IP activity, IP hopping, and geographical tracking."""
    recent_ips_15m: List[str] = field(default_factory=list)
    last_ip: Optional[str] = None
    ip_changed: bool = False
    distinct_ips_15m: int = 1
    recent_countries_24h: List[str] = field(default_factory=list)
    is_foreign_transaction: bool = False


@dataclass
class BehavioralCounters:
    """Real-time failure counters and risk flags."""
    failed_auth_5m: int = 0
    failed_auth_1h: int = 0
    consecutive_failures: int = 0
    high_risk_flags_24h: int = 0
    total_transactions_seen: int = 1


@dataclass
class HotFeatureVector:
    """
    Consolidated real-time feature vector served from Redis for ML inference and decisioning.
    """
    user_key: str
    timestamp: float
    current_amount: float
    velocity: VelocityFeatures = field(default_factory=VelocityFeatures)
    monetary: MonetaryFeatures = field(default_factory=MonetaryFeatures)
    merchant: MerchantFeatures = field(default_factory=MerchantFeatures)
    device: DeviceFeatures = field(default_factory=DeviceFeatures)
    ip: IPFeatures = field(default_factory=IPFeatures)
    behavioral: BehavioralCounters = field(default_factory=BehavioralCounters)

    def to_dict(self) -> Dict[str, Any]:
        """Convert feature vector to flat dictionary representation."""
        return {
            "user_key": self.user_key,
            "timestamp": self.timestamp,
            "current_amount": self.current_amount,
            # Velocity
            "velocity_1m": self.velocity.velocity_1m,
            "velocity_5m": self.velocity.velocity_5m,
            "velocity_15m": self.velocity.velocity_15m,
            "velocity_1h": self.velocity.velocity_1h,
            "velocity_24h": self.velocity.velocity_24h,
            # Monetary
            "rolling_amount_1h": round(self.monetary.rolling_amount_1h, 2),
            "avg_amount_1h": round(self.monetary.avg_amount_1h, 2),
            "max_amount_1h": round(self.monetary.max_amount_1h, 2),
            "rolling_amount_24h": round(self.monetary.rolling_amount_24h, 2),
            "avg_amount_24h": round(self.monetary.avg_amount_24h, 2),
            "amount_deviation_ratio": round(self.monetary.amount_deviation_ratio, 2),
            # Merchant
            "distinct_merchants_1h": self.merchant.distinct_merchants_1h,
            "distinct_categories_1h": self.merchant.distinct_categories_1h,
            # Device
            "device_changed": self.device.device_changed,
            "distinct_devices_15m": self.device.distinct_devices_15m,
            # IP
            "ip_changed": self.ip.ip_changed,
            "distinct_ips_15m": self.ip.distinct_ips_15m,
            "is_foreign_transaction": self.ip.is_foreign_transaction,
            # Behavioral Counters
            "failed_auth_5m": self.behavioral.failed_auth_5m,
            "failed_auth_1h": self.behavioral.failed_auth_1h,
            "consecutive_failures": self.behavioral.consecutive_failures,
            "high_risk_flags_24h": self.behavioral.high_risk_flags_24h,
            "total_transactions_seen": self.behavioral.total_transactions_seen,
        }

    def to_ml_features(self) -> Dict[str, float]:
        """Convert to numerical dictionary suitable for ML model consumption."""
        return {
            "amount": float(self.current_amount),
            "velocity_1m": float(self.velocity.velocity_1m),
            "velocity_5m": float(self.velocity.velocity_5m),
            "velocity_15m": float(self.velocity.velocity_15m),
            "velocity_1h": float(self.velocity.velocity_1h),
            "velocity_24h": float(self.velocity.velocity_24h),
            "rolling_amount_1h": float(self.monetary.rolling_amount_1h),
            "avg_amount_1h": float(self.monetary.avg_amount_1h),
            "max_amount_1h": float(self.monetary.max_amount_1h),
            "rolling_amount_24h": float(self.monetary.rolling_amount_24h),
            "avg_amount_24h": float(self.monetary.avg_amount_24h),
            "amount_deviation_ratio": float(self.monetary.amount_deviation_ratio),
            "distinct_merchants_1h": float(self.merchant.distinct_merchants_1h),
            "distinct_categories_1h": float(self.merchant.distinct_categories_1h),
            "device_changed": 1.0 if self.device.device_changed else 0.0,
            "distinct_devices_15m": float(self.device.distinct_devices_15m),
            "ip_changed": 1.0 if self.ip.ip_changed else 0.0,
            "distinct_ips_15m": float(self.ip.distinct_ips_15m),
            "is_foreign_transaction": 1.0 if self.ip.is_foreign_transaction else 0.0,
            "failed_auth_5m": float(self.behavioral.failed_auth_5m),
            "failed_auth_1h": float(self.behavioral.failed_auth_1h),
            "consecutive_failures": float(self.behavioral.consecutive_failures),
            "high_risk_flags_24h": float(self.behavioral.high_risk_flags_24h),
            "total_transactions_seen": float(self.behavioral.total_transactions_seen),
        }
