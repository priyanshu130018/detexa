"""
flink/windows/behavioral_window.py
─────────────────────────────────────────────────────────────────────────────
Reusable stateful sliding window calculations for failed transaction tracking,
device & IP changes, and unusual transaction timing.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set


class BehavioralWindowCalculator:
    """
    Tracks failed authentication/transaction bursts, rapid hardware/IP switching,
    merchant category diversity, and diurnal timing anomalies.
    """

    @staticmethod
    def calculate_behavioral_metrics(
        recent_transactions: List[Dict[str, Any]],
        failed_attempts: List[float],
        current_device: Optional[str],
        current_ip: Optional[str],
        current_ts: float,
    ) -> Dict[str, Any]:
        # 1. Failed Transaction Counts (5-minute and 1-hour windows)
        failed_5m = sum(1 for ts in failed_attempts if (current_ts - ts) <= 300)
        failed_1h = sum(1 for ts in failed_attempts if (current_ts - ts) <= 3600)

        # 2. Device & IP Tracking in last 15 minutes (900 seconds)
        devices_15m: Set[str] = set()
        ips_15m: Set[str] = set()
        merchants_1h: Set[str] = set()
        categories_1h: Set[str] = set()

        last_txn_ts: Optional[float] = None

        for txn in recent_transactions:
            delta_sec = current_ts - txn.get("timestamp", 0.0)

            if delta_sec <= 900:
                dev = txn.get("device_fingerprint")
                if dev:
                    devices_15m.add(dev)
                ip = txn.get("ip_address")
                if ip:
                    ips_15m.add(ip)

            if delta_sec <= 3600:
                m = txn.get("merchant")
                if m:
                    merchants_1h.add(m)
                c = txn.get("category")
                if c:
                    categories_1h.add(c)

            if txn.get("timestamp") != current_ts:
                if last_txn_ts is None or txn.get("timestamp", 0.0) > last_txn_ts:
                    last_txn_ts = txn.get("timestamp")

        # Check if current device / IP is different from previous in recent window
        device_changed = bool(devices_15m and current_device and current_device not in devices_15m)
        ip_changed = bool(ips_15m and current_ip and current_ip not in ips_15m)

        if current_device:
            devices_15m.add(current_device)
        if current_ip:
            ips_15m.add(current_ip)

        # 3. Unusual Transaction Timing (Diurnal Off-Peak Hours: 02:00 - 05:00 UTC/local)
        dt = datetime.fromtimestamp(current_ts, tz=timezone.utc)
        hour_of_day = dt.hour + (dt.minute / 60.0) + (dt.second / 3600.0)
        is_unusual_hour = (2.0 <= hour_of_day <= 5.0)  # High fraud rate nighttime window

        sin_hour = math.sin(2 * math.pi * hour_of_day / 24.0)
        cos_hour = math.cos(2 * math.pi * hour_of_day / 24.0)

        seconds_since_last = (current_ts - last_txn_ts) if last_txn_ts else 0.0

        return {
            "failed_txn_count_5m": failed_5m,
            "failed_txn_count_1h": failed_1h,
            "distinct_devices_15m": max(1, len(devices_15m)),
            "device_changed": device_changed,
            "distinct_ips_15m": max(1, len(ips_15m)),
            "ip_changed": ip_changed,
            "distinct_merchants_1h": max(1, len(merchants_1h)),
            "distinct_categories_1h": max(1, len(categories_1h)),
            "is_unusual_hour": is_unusual_hour,
            "hour_of_day": round(hour_of_day, 2),
            "sin_hour": round(sin_hour, 4),
            "cos_hour": round(cos_hour, 4),
            "seconds_since_last_txn": round(seconds_since_last, 1),
        }
