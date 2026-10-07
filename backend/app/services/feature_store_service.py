"""
app/services/feature_store_service.py
─────────────────────────────────────────────────────────────────────────────
Service layer adapter for the Redis Real-Time Feature Store.
Enables dependency injection in FastAPI route handlers.
"""

from typing import Any, Dict, Optional

from app.feature_store import (
    HotFeatureVector,
    RedisFeatureStoreService,
    get_feature_store,
)


class FeatureStoreService:
    """FastAPI Service dependency wrapper around the Redis Feature Store."""

    def __init__(self, fs: Optional[RedisFeatureStoreService] = None):
        self.fs = fs or get_feature_store()

    def ingest(
        self,
        user_key: str,
        amount: float,
        merchant: str = "Online Merchant",
        category: str = "General",
        country: str = "US",
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        is_failed: bool = False,
        timestamp: Optional[float] = None,
    ) -> bool:
        return self.fs.ingest_transaction(
            user_key=user_key,
            amount=amount,
            merchant=merchant,
            category=category,
            country=country,
            device_fingerprint=device_fingerprint,
            ip_address=ip_address,
            is_failed=is_failed,
            timestamp=timestamp,
        )

    def fetch_features(
        self,
        user_key: str,
        current_amount: float,
        current_merchant: str = "Online Merchant",
        current_category: str = "General",
        current_device: Optional[str] = None,
        current_ip: Optional[str] = None,
        current_country: str = "US",
        timestamp: Optional[float] = None,
    ) -> HotFeatureVector:
        return self.fs.get_hot_features(
            user_key=user_key,
            current_amount=current_amount,
            current_merchant=current_merchant,
            current_category=current_category,
            current_device=current_device,
            current_ip=current_ip,
            current_country=current_country,
            timestamp=timestamp,
        )

    def record_failure(
        self,
        user_key: str,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
    ) -> bool:
        return self.fs.record_auth_failure(
            user_key=user_key,
            ip_address=ip_address,
            device_fingerprint=device_fingerprint,
        )

    def get_summary(self, user_key: str) -> Dict[str, Any]:
        return self.fs.get_user_summary(user_key)

    def health(self) -> Dict[str, Any]:
        return self.fs.health_check()
