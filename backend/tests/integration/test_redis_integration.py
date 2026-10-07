"""
backend/tests/integration/test_redis_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests connecting directly to the real Redis service.
"""

import pytest
import time
import uuid
import redis


@pytest.mark.integration
class TestRedisIntegration:
    @classmethod
    def setup_class(cls):
        # Connect to real redis container (localhost:6379 on host, redis:6379 in docker)
        try:
            cls.r = redis.Redis(host="localhost", port=6379, socket_timeout=3.0, decode_responses=True)
            cls.r.ping()
        except Exception:
            cls.r = redis.Redis(host="redis", port=6379, socket_timeout=3.0, decode_responses=True)
            cls.r.ping()

    def test_redis_ping_and_server_info(self):
        assert self.r.ping() is True
        info = self.r.info()
        assert "redis_version" in info

    def test_feature_store_read_write_and_ttl(self):
        user_id = f"test_usr_{uuid.uuid4().hex[:6]}"
        key = f"features:user:{user_id}"
        mapping = {
            "tx_count_1h": "3",
            "tx_sum_1h": "450.00",
            "avg_tx_amount_30d": "80.00",
            "last_tx_timestamp": str(int(time.time())),
        }
        self.r.hset(key, mapping=mapping)
        self.r.expire(key, 120)

        retrieved = self.r.hgetall(key)
        assert retrieved["tx_count_1h"] == "3"
        assert float(retrieved["tx_sum_1h"]) == 450.00

        ttl = self.r.ttl(key)
        assert 0 < ttl <= 120

        # Clean up
        self.r.delete(key)

    def test_sliding_window_velocity_sorted_set(self):
        user_id = f"vel_usr_{uuid.uuid4().hex[:6]}"
        zkey = f"velocity:{user_id}:1h"
        now = time.time()

        # Add transactions
        self.r.zadd(zkey, {
            "tx_old": now - 120,
            "tx_recent_1": now - 30,
            "tx_recent_2": now - 10,
            "tx_now": now,
        })
        self.r.expire(zkey, 300)

        # Count events in the last 60 seconds
        count_60s = self.r.zcount(zkey, now - 60, "+inf")
        assert count_60s == 3

        # Count events in the last 5 minutes
        count_300s = self.r.zcount(zkey, now - 300, "+inf")
        assert count_300s == 4

        # Clean up
        self.r.delete(zkey)
