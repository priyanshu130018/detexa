"""
app/api/v1/endpoints/feature_store.py
─────────────────────────────────────────────────────────────────────────────
REST endpoints for inspecting, serving, and managing the Redis Real-Time Feature Store.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.db.models import User
from app.feature_store import (
    HotFeatureVector,
    RedisFeatureStoreService,
    get_feature_store,
)

router = APIRouter()


def get_feature_store_dep() -> RedisFeatureStoreService:
    return get_feature_store()


@router.get(
    "/{user_key}",
    summary="Get real-time hot features for user/card",
    description="Retrieves computed sliding window velocity, monetary, merchant, device, IP, and behavioral features from Redis.",
)
def get_user_hot_features(
    user_key: str,
    amount: float = Query(0.0, description="Current transaction amount to evaluate"),
    merchant: str = Query("Online Merchant", description="Current merchant name"),
    category: str = Query("General", description="Current merchant category"),
    device_fingerprint: Optional[str] = Query(None, description="Current device fingerprint"),
    ip_address: Optional[str] = Query(None, description="Current IP address"),
    country: str = Query("US", description="Current country code"),
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    hot_vector: HotFeatureVector = fs.get_hot_features(
        user_key=user_key,
        current_amount=amount,
        current_merchant=merchant,
        current_category=category,
        current_device=device_fingerprint,
        current_ip=ip_address,
        current_country=country,
    )
    return {
        "user_key": user_key,
        "features": hot_vector.to_dict(),
        "ml_features": hot_vector.to_ml_features(),
    }


@router.get(
    "/{user_key}/summary",
    summary="Get live feature store summary",
    description="Returns aggregate live counters and last seen metadata from Redis for a user/card key.",
)
def get_user_feature_summary(
    user_key: str,
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    return fs.get_user_summary(user_key)


@router.post(
    "/{user_key}/failure",
    status_code=status.HTTP_201_CREATED,
    summary="Record auth or card decline failure",
    description="Increments failure counters and appends a failed attempt to the sliding 1-hour Redis sorted set.",
)
def record_failure_event(
    user_key: str,
    ip_address: Optional[str] = Query(None),
    device_fingerprint: Optional[str] = Query(None),
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    success = fs.record_auth_failure(
        user_key=user_key,
        ip_address=ip_address,
        device_fingerprint=device_fingerprint,
    )
    return {"user_key": user_key, "recorded": success, "event": "AUTH_FAILURE"}


@router.delete(
    "/{user_key}",
    summary="Purge user feature store keys",
    description="Purges all hot feature keys in Redis associated with the user/card key (Admin/Investigation).",
)
def purge_user_feature_store(
    user_key: str,
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    success = fs.purge_user_features(user_key)
    return {"user_key": user_key, "purged": success}


@router.get(
    "/schema/metadata",
    summary="Get canonical feature schema specification",
    description="Returns canonical feature schema metadata, version (3.0.0), group counts, and feature definitions.",
)
def get_feature_schema_metadata() -> Dict[str, Any]:
    from app.features import UnifiedFraudFeatureBuilder
    return UnifiedFraudFeatureBuilder.get_schema_metadata()


@router.get(
    "/vector/{user_key}",
    summary="Get unified full feature vector",
    description="Constructs and returns the complete 5-category canonical feature vector combining transaction, temporal, behavioral, Redis, and Neo4j graph features.",
)
def get_unified_feature_vector(
    user_key: str,
    amount: float = Query(0.0),
    merchant: str = Query("Online Merchant"),
    category: str = Query("General"),
    device_fingerprint: Optional[str] = Query(None),
    ip_address: Optional[str] = Query(None),
    country: str = Query("US"),
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    from app.features import UnifiedFraudFeatureBuilder
    from app.graph import get_graph_service

    # Fetch Redis hot features
    redis_hot = fs.get_hot_features(
        user_key=user_key,
        current_amount=amount,
        current_merchant=merchant,
        current_category=category,
        current_device=device_fingerprint,
        current_ip=ip_address,
        current_country=country,
    )

    # Fetch Neo4j graph features
    graph_feats = get_graph_service().get_features(
        user_id=user_key,
        current_device_fp=device_fingerprint,
        current_ip=ip_address,
    )

    # Construct unified vector
    vector = UnifiedFraudFeatureBuilder.build_realtime_vector(
        payload={
            "user_id": user_key,
            "amount": amount,
            "merchant": merchant,
            "category": category,
            "device_fingerprint": device_fingerprint,
            "ip_address": ip_address,
            "country": country,
        },
        redis_features=redis_hot,
        graph_features=graph_feats,
    )

    return vector.to_inference_dict()


@router.get(
    "/health/status",
    summary="Redis Feature Store health check",
    description="Checks connection status, latency, memory utilization, and feature key counts in Redis.",
)
def get_feature_store_health(
    fs: RedisFeatureStoreService = Depends(get_feature_store_dep),
) -> Dict[str, Any]:
    return fs.health_check()

