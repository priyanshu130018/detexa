"""
app/feature_store/service.py
─────────────────────────────────────────────────────────────────────────────
Real-Time Feature Store Service powered by Redis.

Stores and serves low-latency hot features for fraud detection:
- Transaction velocity (1m, 5m, 15m, 1h, 24h)
- Rolling monetary metrics (sum, avg, max, deviation ratio)
- Merchant & category diversity
- Device fingerprint tracking & hardware hopping
- IP activity & rapid hopping
- Behavioral failure & risk counters

Features:
- Pipelined atomic multi-key reads & writes (<2ms latency)
- Dynamic TTL enforcement from settings (.env)
- Safe serialization of complex Python objects
- Graceful degradation and fallback if Redis is disabled or offline
"""

from datetime import datetime, timezone
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.feature_store.keys import FeatureKeyBuilder
from app.feature_store.models import (
    BehavioralCounters,
    DeviceFeatures,
    HotFeatureVector,
    IPFeatures,
    MerchantFeatures,
    MonetaryFeatures,
    VelocityFeatures,
)
from app.feature_store.serializer import FeatureSerializer


class RedisFeatureStoreService:
    """
    Enterprise Redis Feature Store Service for real-time fraud feature serving.
    """

    def __init__(self):
        self.settings = settings
        # In-memory fallback dictionary for when Redis is unavailable
        self._fallback_store: Dict[str, Dict[str, Any]] = {}

    @property
    def is_enabled(self) -> bool:
        return bool(self.settings.redis_enabled)

    def _get_client(self):
        if not self.is_enabled:
            return None
        return get_redis_client()

    # ── 1. Feature Ingestion (Write Path) ────────────────────────────────────

    def ingest_transaction(
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
        """
        Atomically ingests a transaction into Redis hot feature collections using a Redis pipeline.
        Enforces respective TTLs and trims historical entries beyond the sliding window.
        """
        ts = timestamp or time.time()
        client = self._get_client()

        # Fallback path if Redis is unavailable or disabled
        if client is None:
            if self.is_enabled:
                logger.warning(
                    f"Redis is enabled but connection is unreachable at {self.settings.redis_url}. "
                    f"Falling back to in-memory store for user '{user_key}'."
                )
            self._fallback_ingest(
                user_key=user_key,
                amount=amount,
                merchant=merchant,
                category=category,
                country=country,
                device_fp=device_fingerprint,
                ip_addr=ip_address,
                is_failed=is_failed,
                timestamp=ts,
            )
            return True

        txns_key = FeatureKeyBuilder.transactions_zset_key(user_key)
        fails_key = FeatureKeyBuilder.failed_auth_zset_key(user_key)
        merch_key = FeatureKeyBuilder.merchants_set_key(user_key)
        cat_key = FeatureKeyBuilder.categories_set_key(user_key)
        dev_key = FeatureKeyBuilder.devices_set_key(user_key)
        ip_key = FeatureKeyBuilder.ips_set_key(user_key)
        geo_key = FeatureKeyBuilder.countries_set_key(user_key)
        counters_key = FeatureKeyBuilder.counters_hash_key(user_key)
        latest_key = FeatureKeyBuilder.latest_state_hash_key(user_key)

        txn_payload = FeatureSerializer.dumps({
            "ts": ts,
            "amt": amount,
            "merch": merchant,
            "cat": category,
            "dev": device_fingerprint,
            "ip": ip_address,
            "geo": country,
            "failed": is_failed,
        })

        try:
            pipe = client.pipeline(transaction=True)

            # 1. Transactions Sorted Set (24h window)
            pipe.zadd(txns_key, {txn_payload: ts})
            # Trim elements older than 24 hours (86400s)
            pipe.zremrangebyscore(txns_key, 0, ts - 86400)
            pipe.expire(txns_key, self.settings.redis_fs_ttl_transactions_sec)

            # 2. Failed Auth Sorted Set (1h window)
            if is_failed:
                pipe.zadd(fails_key, {str(ts): ts})
                pipe.zremrangebyscore(fails_key, 0, ts - 3600)
                pipe.expire(fails_key, self.settings.redis_fs_ttl_failures_sec)
                pipe.hincrby(counters_key, "consecutive_failures", 1)
                pipe.hincrby(counters_key, "total_failed_txns", 1)
            else:
                # Reset consecutive failure counter on successful transaction
                pipe.hset(counters_key, "consecutive_failures", "0")

            # 3. Entity Sets with TTL
            if merchant:
                pipe.sadd(merch_key, merchant)
                pipe.expire(merch_key, self.settings.redis_fs_ttl_merchants_sec)
            if category:
                pipe.sadd(cat_key, category)
                pipe.expire(cat_key, self.settings.redis_fs_ttl_merchants_sec)
            if device_fingerprint:
                pipe.sadd(dev_key, device_fingerprint)
                pipe.expire(dev_key, self.settings.redis_fs_ttl_devices_sec)
            if ip_address and ip_address not in ("0.0.0.0", ""):
                pipe.sadd(ip_key, ip_address)
                pipe.expire(ip_key, self.settings.redis_fs_ttl_ips_sec)
            if country:
                pipe.sadd(geo_key, country)
                pipe.expire(geo_key, self.settings.redis_fs_ttl_transactions_sec)

            # 4. Behavioral Counters Hash
            pipe.hincrby(counters_key, "total_txns_seen", 1)
            pipe.expire(counters_key, self.settings.redis_fs_ttl_counters_sec)

            # 5. Latest State Hash
            latest_payload = {
                "last_amount": amount,
                "last_merchant": merchant,
                "last_device": device_fingerprint or "",
                "last_ip": ip_address or "",
                "last_country": country,
                "last_ts": ts,
            }
            pipe.hset(latest_key, mapping=FeatureSerializer.encode_dict_for_hash(latest_payload))
            pipe.expire(latest_key, self.settings.redis_fs_ttl_transactions_sec)

            pipe.execute()
            return True
        except Exception as exc:
            logger.warning(f"Redis Feature Store ingest error for {user_key}: {exc}. Using fallback.")
            self._fallback_ingest(
                user_key=user_key,
                amount=amount,
                merchant=merchant,
                category=category,
                country=country,
                device_fp=device_fingerprint,
                ip_addr=ip_address,
                is_failed=is_failed,
                timestamp=ts,
            )
            return False

    # ── 2. Feature Retrieval & Serving (Read Path) ───────────────────────────

    def get_hot_features(
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
        """
        Retrieves and computes sliding-window features for real-time ML scoring in a single roundtrip.
        """
        ts = timestamp or time.time()
        client = self._get_client()

        if client is None:
            if self.is_enabled:
                logger.warning(
                    f"Redis is enabled but connection is unreachable at {self.settings.redis_url}. "
                    f"Serving hot features from in-memory fallback store for user '{user_key}'."
                )
            return self._fallback_get_features(
                user_key=user_key,
                current_amount=current_amount,
                current_device=current_device,
                current_ip=current_ip,
                current_country=current_country,
                timestamp=ts,
            )

        txns_key = FeatureKeyBuilder.transactions_zset_key(user_key)
        fails_key = FeatureKeyBuilder.failed_auth_zset_key(user_key)
        merch_key = FeatureKeyBuilder.merchants_set_key(user_key)
        cat_key = FeatureKeyBuilder.categories_set_key(user_key)
        dev_key = FeatureKeyBuilder.devices_set_key(user_key)
        ip_key = FeatureKeyBuilder.ips_set_key(user_key)
        geo_key = FeatureKeyBuilder.countries_set_key(user_key)
        counters_key = FeatureKeyBuilder.counters_hash_key(user_key)
        latest_key = FeatureKeyBuilder.latest_state_hash_key(user_key)

        try:
            pipe = client.pipeline(transaction=False)
            # 1. Fetch 24h transactions (with scores)
            pipe.zrangebyscore(txns_key, min=ts - 86400, max=ts, withscores=True)
            # 2. Fetch 1h failed auths
            pipe.zrangebyscore(fails_key, min=ts - 3600, max=ts, withscores=True)
            # 3. Fetch distinct sets
            pipe.smembers(merch_key)
            pipe.smembers(cat_key)
            pipe.smembers(dev_key)
            pipe.smembers(ip_key)
            pipe.smembers(geo_key)
            # 4. Fetch counters and latest metadata
            pipe.hgetall(counters_key)
            pipe.hgetall(latest_key)

            results = pipe.execute()

            raw_txns = results[0]  # List of (payload_str, score)
            raw_fails = results[1]
            merchants_set = results[2] or set()
            categories_set = results[3] or set()
            devices_set = results[4] or set()
            ips_set = results[5] or set()
            countries_set = results[6] or set()
            counters_raw = results[7] or {}
            latest_raw = results[8] or {}

            # Parse transaction history
            txns: List[Dict[str, Any]] = []
            for item in raw_txns:
                payload_str = item[0] if isinstance(item, (list, tuple)) else item
                score = item[1] if isinstance(item, (list, tuple)) else ts
                parsed = FeatureSerializer.loads(payload_str)
                if isinstance(parsed, dict):
                    parsed["ts"] = score
                    txns.append(parsed)

            # ── 1. Multi-scale Velocity ──────────────────────────────────────
            # Include current transaction in counts
            v_1m = sum(1 for t in txns if (ts - t["ts"]) <= 60) + 1
            v_5m = sum(1 for t in txns if (ts - t["ts"]) <= 300) + 1
            v_15m = sum(1 for t in txns if (ts - t["ts"]) <= 900) + 1
            v_1h = sum(1 for t in txns if (ts - t["ts"]) <= 3600) + 1
            v_24h = len(txns) + 1

            vel_feat = VelocityFeatures(
                velocity_1m=v_1m,
                velocity_5m=v_5m,
                velocity_15m=v_15m,
                velocity_1h=v_1h,
                velocity_24h=v_24h,
            )

            # ── 2. Monetary Statistics ───────────────────────────────────────
            txns_1h = [t for t in txns if (ts - t["ts"]) <= 3600]
            amounts_1h = [float(t.get("amt", 0.0)) for t in txns_1h] + [current_amount]
            amounts_24h = [float(t.get("amt", 0.0)) for t in txns] + [current_amount]

            sum_1h = sum(amounts_1h)
            avg_1h = sum_1h / len(amounts_1h) if amounts_1h else current_amount
            max_1h = max(amounts_1h) if amounts_1h else current_amount

            sum_24h = sum(amounts_24h)
            avg_24h = sum_24h / len(amounts_24h) if amounts_24h else current_amount

            baseline_avg = max(avg_1h, 10.0)
            amount_deviation = current_amount / baseline_avg

            mon_feat = MonetaryFeatures(
                rolling_amount_1h=sum_1h,
                avg_amount_1h=avg_1h,
                max_amount_1h=max_1h,
                rolling_amount_24h=sum_24h,
                avg_amount_24h=avg_24h,
                amount_deviation_ratio=amount_deviation,
            )

            # ── 3. Merchant & Category Diversity ─────────────────────────────
            all_merchants = set(merchants_set)
            all_merchants.add(current_merchant)
            all_categories = set(categories_set)
            all_categories.add(current_category)

            merch_feat = MerchantFeatures(
                recent_merchants_1h=list(all_merchants),
                distinct_merchants_1h=len(all_merchants),
                recent_categories_1h=list(all_categories),
                distinct_categories_1h=len(all_categories),
            )

            # ── 4. Device Features ───────────────────────────────────────────
            last_device = latest_raw.get("last_device") if latest_raw else None
            device_changed = bool(last_device and current_device and last_device != current_device)
            devs_15m = set(
                t.get("dev") for t in txns if t.get("dev") and (ts - t["ts"]) <= 900
            )
            if current_device:
                devs_15m.add(current_device)

            dev_feat = DeviceFeatures(
                recent_devices_15m=list(devs_15m),
                last_device=last_device,
                device_changed=device_changed,
                distinct_devices_15m=len(devs_15m) if devs_15m else 1,
            )

            # ── 5. IP & Geo Features ─────────────────────────────────────────
            last_ip = latest_raw.get("last_ip") if latest_raw else None
            ip_changed = bool(last_ip and current_ip and last_ip != current_ip)
            ips_15m = set(
                t.get("ip") for t in txns if t.get("ip") and (ts - t["ts"]) <= 900
            )
            if current_ip:
                ips_15m.add(current_ip)

            countries_list = list(countries_set)
            if current_country:
                countries_list.append(current_country)
            is_foreign = len(set(countries_list)) > 1

            ip_feat = IPFeatures(
                recent_ips_15m=list(ips_15m),
                last_ip=last_ip,
                ip_changed=ip_changed,
                distinct_ips_15m=len(ips_15m) if ips_15m else 1,
                recent_countries_24h=list(set(countries_list)),
                is_foreign_transaction=is_foreign,
            )

            # ── 6. Behavioral Counters ───────────────────────────────────────
            fail_scores = [item[1] if isinstance(item, (list, tuple)) else float(item) for item in raw_fails]
            failed_5m = sum(1 for f_ts in fail_scores if (ts - f_ts) <= 300)
            failed_1h = len(fail_scores)

            consecutive_fails = int(counters_raw.get("consecutive_failures", 0))
            high_risk_flags = int(counters_raw.get("high_risk_flags_24h", 0))
            total_seen = int(counters_raw.get("total_txns_seen", 0)) + 1

            beh_counters = BehavioralCounters(
                failed_auth_5m=failed_5m,
                failed_auth_1h=failed_1h,
                consecutive_failures=consecutive_fails,
                high_risk_flags_24h=high_risk_flags,
                total_transactions_seen=total_seen,
            )

            return HotFeatureVector(
                user_key=user_key,
                timestamp=ts,
                current_amount=current_amount,
                velocity=vel_feat,
                monetary=mon_feat,
                merchant=merch_feat,
                device=dev_feat,
                ip=ip_feat,
                behavioral=beh_counters,
            )

        except Exception as exc:
            logger.warning(f"Redis Feature Store get_hot_features error for {user_key}: {exc}. Fallback active.")
            return self._fallback_get_features(
                user_key=user_key,
                current_amount=current_amount,
                current_device=current_device,
                current_ip=current_ip,
                current_country=current_country,
                timestamp=ts,
            )

    # ── 3. Specialized Helper Methods ────────────────────────────────────────

    def record_auth_failure(
        self,
        user_key: str,
        ip_address: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Records an authentication / card decline failure into Redis."""
        ts = timestamp or time.time()
        client = self._get_client()
        if client is None:
            return True

        fails_key = FeatureKeyBuilder.failed_auth_zset_key(user_key)
        counters_key = FeatureKeyBuilder.counters_hash_key(user_key)

        try:
            pipe = client.pipeline(transaction=True)
            pipe.zadd(fails_key, {str(ts): ts})
            pipe.zremrangebyscore(fails_key, 0, ts - 3600)
            pipe.expire(fails_key, self.settings.redis_fs_ttl_failures_sec)
            pipe.hincrby(counters_key, "consecutive_failures", 1)
            pipe.hincrby(counters_key, "total_failed_txns", 1)
            pipe.expire(counters_key, self.settings.redis_fs_ttl_counters_sec)
            pipe.execute()
            return True
        except Exception as exc:
            logger.debug(f"Failed to record auth failure in Redis for {user_key}: {exc}")
            return False

    def record_risk_decision(
        self,
        user_key: str,
        risk_level: str,
        decision: str,
    ) -> bool:
        """Updates high risk counters in Redis for decision tracking."""
        if risk_level not in ("Medium", "High") and decision not in ("REVIEW", "BLOCK"):
            return True

        client = self._get_client()
        if client is None:
            return True

        counters_key = FeatureKeyBuilder.counters_hash_key(user_key)
        try:
            pipe = client.pipeline(transaction=True)
            pipe.hincrby(counters_key, "high_risk_flags_24h", 1)
            pipe.expire(counters_key, self.settings.redis_fs_ttl_counters_sec)
            pipe.execute()
            return True
        except Exception as exc:
            logger.debug(f"Failed to record risk decision in Redis for {user_key}: {exc}")
            return False

    def purge_user_features(self, user_key: str) -> bool:
        """Purges all feature store keys for a given user."""
        client = self._get_client()
        if client is None:
            self._fallback_store.pop(user_key, None)
            return True

        pattern = FeatureKeyBuilder.user_pattern(user_key)
        try:
            keys = client.keys(pattern)
            if keys:
                client.delete(*keys)
            return True
        except Exception as exc:
            logger.debug(f"Error purging features for {user_key}: {exc}")
            return False

    def get_user_summary(self, user_key: str) -> Dict[str, Any]:
        """Returns live metadata and metrics summary for dashboards and investigation."""
        client = self._get_client()
        if client is None:
            return {"user_key": user_key, "status": "redis_offline", "total_txns": 0}

        counters_key = FeatureKeyBuilder.counters_hash_key(user_key)
        latest_key = FeatureKeyBuilder.latest_state_hash_key(user_key)
        try:
            pipe = client.pipeline(transaction=False)
            pipe.hgetall(counters_key)
            pipe.hgetall(latest_key)
            res = pipe.execute()
            counters = res[0] or {}
            latest = res[1] or {}
            return {
                "user_key": user_key,
                "status": "active",
                "total_txns": int(counters.get("total_txns_seen", 0)),
                "consecutive_failures": int(counters.get("consecutive_failures", 0)),
                "high_risk_flags_24h": int(counters.get("high_risk_flags_24h", 0)),
                "last_amount": float(latest.get("last_amount", 0.0)) if latest.get("last_amount") else None,
                "last_merchant": latest.get("last_merchant"),
                "last_seen_ts": float(latest.get("last_ts", 0.0)) if latest.get("last_ts") else None,
            }
        except Exception as exc:
            return {"user_key": user_key, "status": "error", "error": str(exc)}

    def health_check(self) -> Dict[str, Any]:
        """Returns Redis connection status, memory stats, and feature store metrics."""
        client = self._get_client()
        if not self.is_enabled:
            return {"status": "disabled", "enabled": False}
        if client is None:
            return {"status": "unreachable", "enabled": True}

        try:
            start = time.time()
            client.ping()
            latency_ms = round((time.time() - start) * 1000.0, 2)
            info = client.info(section="memory")
            keys_count = len(client.keys(f"{FeatureKeyBuilder.PREFIX}:*"))
            return {
                "status": "healthy",
                "enabled": True,
                "ping_latency_ms": latency_ms,
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "feature_keys_count": keys_count,
            }
        except Exception as exc:
            return {"status": "degraded", "enabled": True, "error": str(exc)}

    # ── 4. In-Memory Fallback Implementation ─────────────────────────────────

    def _fallback_ingest(
        self,
        user_key: str,
        amount: float,
        merchant: str,
        category: str,
        country: str,
        device_fp: Optional[str],
        ip_addr: Optional[str],
        is_failed: bool,
        timestamp: float,
    ):
        if user_key not in self._fallback_store:
            self._fallback_store[user_key] = {
                "txns": [],
                "fails": [],
                "latest": {},
                "counters": {"total": 0, "consecutive_fails": 0, "risk_flags": 0},
            }

        st = self._fallback_store[user_key]
        st["txns"].append({
            "ts": timestamp,
            "amt": amount,
            "merch": merchant,
            "cat": category,
            "dev": device_fp,
            "ip": ip_addr,
            "geo": country,
            "failed": is_failed,
        })
        # Keep last 100 transactions
        st["txns"] = [t for t in st["txns"] if (timestamp - t["ts"]) <= 86400][-100:]
        st["counters"]["total"] += 1

        if is_failed:
            st["fails"].append(timestamp)
            st["fails"] = [f for f in st["fails"] if (timestamp - f) <= 3600]
            st["counters"]["consecutive_fails"] += 1
        else:
            st["counters"]["consecutive_fails"] = 0

        st["latest"] = {
            "last_amount": amount,
            "last_merchant": merchant,
            "last_device": device_fp,
            "last_ip": ip_addr,
            "last_country": country,
            "last_ts": timestamp,
        }

    def _fallback_get_features(
        self,
        user_key: str,
        current_amount: float,
        current_device: Optional[str],
        current_ip: Optional[str],
        current_country: str,
        timestamp: float,
    ) -> HotFeatureVector:
        st = self._fallback_store.get(user_key, {"txns": [], "fails": [], "latest": {}, "counters": {}})
        txns = st.get("txns", [])
        fails = st.get("fails", [])
        latest = st.get("latest", {})
        counters = st.get("counters", {})

        v_1m = sum(1 for t in txns if (timestamp - t["ts"]) <= 60) + 1
        v_5m = sum(1 for t in txns if (timestamp - t["ts"]) <= 300) + 1
        v_15m = sum(1 for t in txns if (timestamp - t["ts"]) <= 900) + 1
        v_1h = sum(1 for t in txns if (timestamp - t["ts"]) <= 3600) + 1
        v_24h = len(txns) + 1

        amounts_1h = [t["amt"] for t in txns if (timestamp - t["ts"]) <= 3600] + [current_amount]
        sum_1h = sum(amounts_1h)
        avg_1h = sum_1h / len(amounts_1h) if amounts_1h else current_amount
        max_1h = max(amounts_1h) if amounts_1h else current_amount

        amounts_24h = [t["amt"] for t in txns] + [current_amount]
        sum_24h = sum(amounts_24h)
        avg_24h = sum_24h / len(amounts_24h) if amounts_24h else current_amount

        last_device = latest.get("last_device")
        dev_changed = bool(last_device and current_device and last_device != current_device)

        last_ip = latest.get("last_ip")
        ip_changed = bool(last_ip and current_ip and last_ip != current_ip)

        failed_5m = sum(1 for f in fails if (timestamp - f) <= 300)
        failed_1h = len(fails)

        return HotFeatureVector(
            user_key=user_key,
            timestamp=timestamp,
            current_amount=current_amount,
            velocity=VelocityFeatures(velocity_1m=v_1m, velocity_5m=v_5m, velocity_15m=v_15m, velocity_1h=v_1h, velocity_24h=v_24h),
            monetary=MonetaryFeatures(rolling_amount_1h=sum_1h, avg_amount_1h=avg_1h, max_amount_1h=max_1h, rolling_amount_24h=sum_24h, avg_amount_24h=avg_24h, amount_deviation_ratio=current_amount / max(avg_1h, 10.0)),
            merchant=MerchantFeatures(),
            device=DeviceFeatures(last_device=last_device, device_changed=dev_changed, distinct_devices_15m=1),
            ip=IPFeatures(last_ip=last_ip, ip_changed=ip_changed, distinct_ips_15m=1),
            behavioral=BehavioralCounters(
                failed_auth_5m=failed_5m,
                failed_auth_1h=failed_1h,
                consecutive_failures=counters.get("consecutive_fails", 0),
                high_risk_flags_24h=counters.get("risk_flags", 0),
                total_transactions_seen=counters.get("total", 0) + 1,
            ),
        )


_feature_store_instance: Optional[RedisFeatureStoreService] = None


def get_feature_store() -> RedisFeatureStoreService:
    """Returns singleton instance of RedisFeatureStoreService."""
    global _feature_store_instance
    if _feature_store_instance is None:
        _feature_store_instance = RedisFeatureStoreService()
    return _feature_store_instance
