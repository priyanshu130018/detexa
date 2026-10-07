"""
flink/windows/velocity_window.py
─────────────────────────────────────────────────────────────────────────────
Reusable sliding & tumbling window calculations for transaction velocity and frequency.
"""

from typing import Any, Dict, List


class VelocityWindowCalculator:
    """
    Computes transaction frequencies and velocities across multi-scale sliding windows:
    1 minute, 5 minutes, 15 minutes, 1 hour, and 24 hours.
    """

    @staticmethod
    def calculate_velocity_counts(
        recent_transactions: List[Dict[str, Any]],
        current_ts: float,
    ) -> Dict[str, int]:
        """
        Filters recent transaction history to count events within standard time horizons.
        """
        v_1m = 0
        v_5m = 0
        v_15m = 0
        v_1h = 0
        v_24h = 0

        for txn in recent_transactions:
            delta_sec = current_ts - txn.get("timestamp", 0.0)
            if delta_sec < 0:
                delta_sec = 0.0  # Handle slight out-of-order clock skew

            if delta_sec <= 60:
                v_1m += 1
            if delta_sec <= 300:
                v_5m += 1
            if delta_sec <= 900:
                v_15m += 1
            if delta_sec <= 3600:
                v_1h += 1
            if delta_sec <= 86400:
                v_24h += 1

        return {
            "velocity_1m": max(1, v_1m),
            "velocity_5m": max(1, v_5m),
            "velocity_15m": max(1, v_15m),
            "velocity_1h": max(1, v_1h),
            "velocity_24h": max(1, v_24h),
        }
