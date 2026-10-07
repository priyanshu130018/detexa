"""
backend/tests/integration/test_flink_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests connecting directly to Apache Flink and sliding window processing.
"""

import pytest
import time
import httpx
from app.streaming.flink_processor import SlidingWindowState, FlinkRealTimeStreamProcessor


@pytest.mark.integration
class TestFlinkIntegration:
    def test_flink_jobmanager_rest_api(self):
        # Query Flink JobManager (localhost:8081 or flink-jobmanager:8081)
        target = "http://localhost:8081"
        try:
            resp = httpx.get(f"{target}/overview", timeout=3.0)
        except Exception:
            target = "http://flink-jobmanager:8081"
            resp = httpx.get(f"{target}/overview", timeout=3.0)

        assert resp.status_code == 200
        data = resp.json()
        assert "taskmanagers" in data
        assert "slots-total" in data

    def test_sliding_window_state_windowed_aggregations(self):
        window = SlidingWindowState()
        user_key = "user-window-test-01"
        now = time.time()

        # Emit 3 events over time
        f1 = window.record_and_compute(user_key, 100.0, "M1", "US", "d1", now - 200)
        f2 = window.record_and_compute(user_key, 200.0, "M2", "US", "d1", now - 50)
        f3 = window.record_and_compute(user_key, 300.0, "M3", "US", "d1", now)

        assert f3.velocity_1h == 3
        assert f3.velocity_5m == 3
        assert f3.velocity_1m == 2
        assert f3.rolling_amount_1h == 600.0
        assert f3.avg_amount_1h == 200.0
        assert f3.distinct_merchants_1h == 3
