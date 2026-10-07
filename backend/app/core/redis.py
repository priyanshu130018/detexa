"""
app/core/redis.py
─────────────────────────────────────────────────────────────────────────────
Thread-safe Redis connection manager, connection pooling, and caching helpers.
Reads configuration from centralized settings (.env).
Gracefully degrades to safe defaults or no-op if Redis is unreachable or disabled.
"""

import json
from typing import Any, Dict, Optional, Union
import redis
from redis.connection import ConnectionPool

from app.core.config import settings
from app.core.logging import logger

_pool: Optional[ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


def get_redis_pool() -> Optional[ConnectionPool]:
    """
    Initializes and returns a thread-safe Redis ConnectionPool singleton.
    """
    global _pool
    if not settings.redis_enabled:
        return None

    if _pool is None:
        try:
            pool_kwargs: Dict[str, Any] = {
                "max_connections": settings.redis_pool_max_connections,
                "socket_timeout": settings.redis_socket_timeout,
                "socket_connect_timeout": settings.redis_socket_connect_timeout,
                "decode_responses": True,
            }
            if settings.redis_password:
                pool_kwargs["password"] = settings.redis_password
            if settings.redis_ssl:
                pool_kwargs["ssl"] = True

            _pool = ConnectionPool.from_url(settings.redis_url, **pool_kwargs)
            logger.info(f"Initialized Redis connection pool (max={settings.redis_pool_max_connections})")
        except Exception as exc:
            logger.warning(f"Failed to create Redis connection pool ({exc}). Running with Redis disabled.")
            _pool = None

    return _pool


def get_redis_client() -> Optional[redis.Redis]:
    """
    Returns a pooled Redis client instance with ping verification and automatic reconnection.
    """
    global _redis_client
    if not settings.redis_enabled:
        return None

    pool = get_redis_pool()
    if pool is None:
        return None

    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None

    try:
        client = redis.Redis(connection_pool=pool)
        client.ping()
        _redis_client = client
        logger.info("Successfully connected to Redis feature store & cache.")
    except Exception as exc:
        logger.warning(f"Redis connection failed ({exc}). Continuing with safe fallback.")
        _redis_client = None

    return _redis_client


def cache_get(key: str) -> Optional[Any]:
    """Retrieve and deserialize JSON value from Redis."""
    client = get_redis_client()
    if client is None:
        return None
    try:
        val = client.get(key)
        if val is not None:
            return json.loads(val)
    except Exception as exc:
        logger.debug(f"Redis cache_get error for key {key}: {exc}")
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> bool:
    """Serialize and write value to Redis with TTL."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception as exc:
        logger.debug(f"Redis cache_set error for key {key}: {exc}")
        return False


def cache_delete(key: str) -> bool:
    """Delete a key from Redis."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.delete(key)
        return True
    except Exception as exc:
        logger.debug(f"Redis cache_delete error for key {key}: {exc}")
        return False


def cache_delete_pattern(pattern: str) -> bool:
    """Delete all keys matching pattern."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
        return True
    except Exception as exc:
        logger.debug(f"Redis cache_delete_pattern error for pattern {pattern}: {exc}")
        return False
