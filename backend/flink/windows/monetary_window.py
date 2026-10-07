"""
flink/windows/monetary_window.py
─────────────────────────────────────────────────────────────────────────────
Reusable sliding window calculations for monetary metrics, rolling statistics,
and deviation ratios.
"""

import math
from typing import Any, Dict, List


class MonetaryWindowCalculator:
    """
    Computes rolling sums, moving averages, standard deviations, and spending
    anomaly ratios over 1-hour and 24-hour sliding windows.
    """

    @staticmethod
    def calculate_monetary_metrics(
        recent_transactions: List[Dict[str, Any]],
        current_amount: float,
        current_ts: float,
    ) -> Dict[str, float]:
        amounts_1h = []
        amounts_24h = []

        for txn in recent_transactions:
            delta_sec = current_ts - txn.get("timestamp", 0.0)
            amt = float(txn.get("amount", 0.0))

            if delta_sec <= 3600:
                amounts_1h.append(amt)
            if delta_sec <= 86400:
                amounts_24h.append(amt)

        # 1-Hour Window Metrics
        rolling_1h = sum(amounts_1h)
        avg_1h = rolling_1h / len(amounts_1h) if amounts_1h else current_amount
        max_1h = max(amounts_1h) if amounts_1h else current_amount

        # 24-Hour Window Metrics
        rolling_24h = sum(amounts_24h)
        avg_24h = rolling_24h / len(amounts_24h) if amounts_24h else current_amount

        # Amount Deviation Ratio (Sudden spikes compared to historical 1h average)
        deviation_ratio = (current_amount / avg_1h) if avg_1h > 0 else 1.0

        return {
            "rolling_amount_1h": round(rolling_1h, 2),
            "avg_amount_1h": round(avg_1h, 2),
            "max_amount_1h": round(max_1h, 2),
            "rolling_amount_24h": round(rolling_24h, 2),
            "avg_amount_24h": round(avg_24h, 2),
            "amount_deviation_ratio": round(deviation_ratio, 2),
        }
