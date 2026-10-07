"""
flink/operators/feature_enrichment_operator.py
─────────────────────────────────────────────────────────────────────────────
Stateful Keyed Feature Enrichment Operator for Apache Flink stream pipelines.
Maintains state per user/card key and extracts multi-scale sliding window features.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from flink.models.state_schemas import FlinkEnrichedEvent, UserStreamState, WindowMetrics
from flink.windows.behavioral_window import BehavioralWindowCalculator
from flink.windows.monetary_window import MonetaryWindowCalculator
from flink.windows.velocity_window import VelocityWindowCalculator


class FeatureEnrichmentOperator:
    """
    Keyed stateful stream operator simulating Flink's KeyedProcessFunction.
    Maintains bounded in-memory sliding state per user/card key.
    """

    def __init__(self, max_history_per_key: int = 200):
        self.max_history = max_history_per_key
        self._state_store: Dict[str, UserStreamState] = {}

    def get_or_create_state(self, user_key: str) -> UserStreamState:
        if user_key not in self._state_store:
            now_ts = time.time()
            self._state_store[user_key] = UserStreamState(
                user_key=user_key,
                total_txns_seen=0,
                first_seen_ts=now_ts,
                last_seen_ts=now_ts,
            )
        return self._state_store[user_key]

    def process_event(self, raw_event_dict: Dict[str, Any]) -> FlinkEnrichedEvent:
        """
        Process incoming raw transaction event:
        1. Extract user key.
        2. Retrieve and update keyed state.
        3. Compute multi-window velocity, monetary, and behavioral features.
        4. Emit FlinkEnrichedEvent.
        """
        header = raw_event_dict.get("header", {})
        payload = raw_event_dict.get("payload", {})

        user_key = (
            header.get("partition_key")
            or payload.get("user_id")
            or payload.get("transaction_ref")
            or "anonymous"
        )
        now_ts = time.time()

        amount = float(payload.get("amount", 0.0))
        merchant = payload.get("merchant", "Online Merchant")
        category = payload.get("category", "General")
        country = payload.get("country", "US")
        device_fp = payload.get("device_fingerprint")
        ip_addr = payload.get("ip_address")
        is_failed = bool(payload.get("is_failed", False))

        state = self.get_or_create_state(user_key)

        # 1. Compute Window Metrics using existing history
        vel_metrics = VelocityWindowCalculator.calculate_velocity_counts(
            recent_transactions=state.recent_transactions,
            current_ts=now_ts,
        )

        mon_metrics = MonetaryWindowCalculator.calculate_monetary_metrics(
            recent_transactions=state.recent_transactions,
            current_amount=amount,
            current_ts=now_ts,
        )

        beh_metrics = BehavioralWindowCalculator.calculate_behavioral_metrics(
            recent_transactions=state.recent_transactions,
            failed_attempts=state.failed_attempts,
            current_device=device_fp,
            current_ip=ip_addr,
            current_ts=now_ts,
        )

        # 2. Update state with current transaction
        state.total_txns_seen += 1
        state.last_seen_ts = now_ts

        current_entry = {
            "timestamp": now_ts,
            "amount": amount,
            "merchant": merchant,
            "category": category,
            "country": country,
            "device_fingerprint": device_fp,
            "ip_address": ip_addr,
            "is_failed": is_failed,
        }

        # Bounded state maintenance: keep last 24h
        state.recent_transactions.append(current_entry)
        state.recent_transactions = [
            t for t in state.recent_transactions if (now_ts - t["timestamp"]) <= 86400
        ][-self.max_history :]

        if is_failed:
            state.failed_attempts.append(now_ts)
            state.failed_attempts = [
                ts for ts in state.failed_attempts if (now_ts - ts) <= 3600
            ]

        # Combine all computed metrics
        window_metrics = WindowMetrics(
            velocity_1m=vel_metrics["velocity_1m"],
            velocity_5m=vel_metrics["velocity_5m"],
            velocity_15m=vel_metrics["velocity_15m"],
            velocity_1h=vel_metrics["velocity_1h"],
            velocity_24h=vel_metrics["velocity_24h"],
            rolling_amount_1h=mon_metrics["rolling_amount_1h"],
            avg_amount_1h=mon_metrics["avg_amount_1h"],
            max_amount_1h=mon_metrics["max_amount_1h"],
            rolling_amount_24h=mon_metrics["rolling_amount_24h"],
            avg_amount_24h=mon_metrics["avg_amount_24h"],
            amount_deviation_ratio=mon_metrics["amount_deviation_ratio"],
            failed_txn_count_5m=beh_metrics["failed_txn_count_5m"],
            failed_txn_count_1h=beh_metrics["failed_txn_count_1h"],
            distinct_devices_15m=beh_metrics["distinct_devices_15m"],
            device_changed=beh_metrics["device_changed"],
            distinct_ips_15m=beh_metrics["distinct_ips_15m"],
            ip_changed=beh_metrics["ip_changed"],
            distinct_merchants_1h=beh_metrics["distinct_merchants_1h"],
            distinct_categories_1h=beh_metrics["distinct_categories_1h"],
            is_unusual_hour=beh_metrics["is_unusual_hour"],
            hour_of_day=beh_metrics["hour_of_day"],
            sin_hour=beh_metrics["sin_hour"],
            cos_hour=beh_metrics["cos_hour"],
            seconds_since_last_txn=beh_metrics["seconds_since_last_txn"],
        )

        pca_features = {f"v{i}": float(payload.get(f"v{i}", payload.get(f"V{i}", 0.0))) for i in range(1, 29)}

        return FlinkEnrichedEvent(
            event_id=header.get("event_id", str(now_ts)),
            idempotency_key=header.get("idempotency_key", str(now_ts)),
            transaction_ref=payload.get("transaction_ref", f"TXN-{int(now_ts * 1000)}"),
            user_id=payload.get("user_id"),
            amount=amount,
            currency=payload.get("currency", "USD"),
            merchant=merchant,
            category=category,
            country=country,
            device_fingerprint=device_fp,
            ip_address=ip_addr,
            pca_features=pca_features,
            window_metrics=window_metrics,
            ingestion_ts=now_ts,
        )
