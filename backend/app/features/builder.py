"""
app/features/builder.py
─────────────────────────────────────────────────────────────────────────────
Unified Fraud Feature Builder for Detexa Platform.
Version: 4.0.0 (Indian Banking Transaction System)

Provides a single, authoritative feature extraction engine shared across:
- Model Training (preventing data leakage and feature skew)
- Batch Offline Inference
- Online Real-Time Inference (FastAPI)
- Streaming Window Ingestion (Apache Flink)

Combines:
1. Core Indian Banking Transaction & Balance Signals
2. Diurnal & Temporal Cyclical Encodings
3. Customer Historical Behavioral Velocity
4. Real-time Redis Sliding Windows
5. Neo4j Graph Relationship & Fraud Ring Features
"""

from datetime import datetime, timezone
import math
import time
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from app.feature_store.models import HotFeatureVector
from app.features.models import UnifiedFeatureVector
from app.features.schema import (
    CANONICAL_FEATURE_DEFINITIONS,
    CANONICAL_FEATURE_NAMES,
    FEATURE_DEFAULT_MAP,
    FEATURE_SCHEMA_VERSION,
    FeatureGroup,
)
from app.graph.models import GraphRiskFeatures


class UnifiedFraudFeatureBuilder:
    """
    Unified Feature Engineering Engine.
    Ensures deterministic, identical feature vectors across training and inference.
    """

    SCHEMA_VERSION = FEATURE_SCHEMA_VERSION

    @classmethod
    def build_realtime_vector(
        cls,
        payload: Dict[str, Any],
        redis_features: Optional[Union[HotFeatureVector, Dict[str, Any]]] = None,
        graph_features: Optional[Union[GraphRiskFeatures, Dict[str, Any]]] = None,
        timestamp: Optional[float] = None,
    ) -> UnifiedFeatureVector:
        """
        Builds a canonical unified feature vector from raw banking payload + optional Redis and Graph sources.
        """
        ts = timestamp or float(payload.get("timestamp", time.time()))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        # ── 1. Transaction Amount & Account Balances ─────────────────────────
        raw_amt = payload.get("transaction_amount", payload.get("amount", payload.get("Amount", 0.0)))
        amount = float(raw_amt) if raw_amt is not None else 0.0
        amount_clean = max(amount, 0.0)

        raw_balance = payload.get("account_balance", payload.get("balance", 50000.0))
        balance = float(raw_balance) if raw_balance is not None else 50000.0
        balance_clean = max(balance, 0.0)

        credit_score = float(payload.get("credit_score", 650.0))
        has_loan = float(payload.get("has_loan", 0.0))
        emi_amt = float(payload.get("emi_amount", 0.0))
        emi_clean = max(emi_amt, 0.0)

        # ── 2. Diurnal & Temporal Features ───────────────────────────────────
        hour_val = payload.get("transaction_hour", payload.get("hour_of_day", dt.hour + dt.minute / 60.0))
        try:
            hour = float(hour_val)
        except (ValueError, TypeError):
            hour = float(dt.hour)

        feat_values: Dict[str, float] = {}

        # Group 1: Transaction & Balance
        feat_values["transaction_amount"] = amount_clean
        feat_values["log_transaction_amount"] = float(np.log1p(amount_clean))
        feat_values["transaction_amount_sq"] = float(amount_clean ** 2)
        feat_values["account_balance"] = balance_clean
        feat_values["log_account_balance"] = float(np.log1p(balance_clean))
        feat_values["amount_to_balance_ratio"] = float(amount_clean / (balance_clean + 1.0))
        feat_values["credit_score"] = credit_score
        feat_values["has_loan"] = has_loan
        feat_values["emi_amount"] = emi_clean
        feat_values["log_emi_amount"] = float(np.log1p(emi_clean))
        feat_values["emi_to_balance_ratio"] = float(emi_clean / (balance_clean + 1.0))
        feat_values["amount_to_emi_ratio"] = float(amount_clean / (emi_clean + 1.0))

        # Group 2: Temporal
        feat_values["transaction_hour"] = hour
        feat_values["hour_sin"] = float(np.sin(2.0 * np.pi * hour / 24.0))
        feat_values["hour_cos"] = float(np.cos(2.0 * np.pi * hour / 24.0))
        feat_values["is_night_txn"] = 1.0 if (hour < 6.0 or hour >= 22.0) else 0.0

        # Group 3: Customer History & Velocity (Defaults for single realtime txn if not provided)
        feat_values["cust_txn_count_prior"] = float(payload.get("cust_txn_count_prior", 1.0))
        feat_values["cust_avg_amount_prior"] = float(payload.get("cust_avg_amount_prior", amount_clean or 25000.0))
        feat_values["cust_amount_diff_from_avg"] = float(payload.get("cust_amount_diff_from_avg", amount_clean - feat_values["cust_avg_amount_prior"]))
        feat_values["cust_amount_ratio_to_avg"] = float(payload.get("cust_amount_ratio_to_avg", amount_clean / (feat_values["cust_avg_amount_prior"] + 1.0)))
        feat_values["cust_time_since_last_txn_hours"] = float(payload.get("cust_time_since_last_txn_hours", 24.0))
        feat_values["cust_channel_change"] = float(payload.get("cust_channel_change", 0.0))
        feat_values["cust_type_change"] = float(payload.get("cust_type_change", 0.0))

        # Group 4: Behavioral & Biometrics
        typing_spd = float(payload.get("typing_speed", 45.0))
        mouse_vel = float(payload.get("mouse_velocity", 250.0))
        failed_lg = float(payload.get("failed_logins", 0.0))
        is_vpn = 1.0 if payload.get("is_vpn") in (True, 1, "true", "True") else 0.0
        is_tor = 1.0 if payload.get("is_tor") in (True, 1, "true", "True") else 0.0
        dev_change = 1.0 if payload.get("device_change") in (True, 1, "true", "True") else 0.0

        feat_values["typing_speed"] = typing_spd
        feat_values["mouse_velocity"] = mouse_vel
        feat_values["failed_logins"] = failed_lg
        feat_values["is_vpn"] = is_vpn
        feat_values["is_tor"] = is_tor
        feat_values["device_change"] = dev_change
        feat_values["risk_combo"] = is_vpn + (2.0 * is_tor) + dev_change

        # Group 5: Redis Real-Time Sliding Windows
        if isinstance(redis_features, HotFeatureVector):
            rf = redis_features
            feat_values["velocity_1m"] = float(rf.velocity_1m)
            feat_values["velocity_5m"] = float(rf.velocity_5m)
            feat_values["velocity_15m"] = float(rf.velocity_15m)
            feat_values["velocity_1h"] = float(rf.velocity_1h)
            feat_values["velocity_24h"] = float(rf.velocity_24h)
            feat_values["rolling_amount_1h"] = float(rf.rolling_amount_1h)
            feat_values["avg_amount_1h"] = float(rf.avg_amount_1h)
            feat_values["max_amount_1h"] = float(rf.max_amount_1h)
            feat_values["rolling_amount_24h"] = float(rf.rolling_amount_24h)
            feat_values["avg_amount_24h"] = float(rf.avg_amount_24h)
            feat_values["amount_deviation_ratio"] = float(rf.amount_deviation_ratio)
            feat_values["distinct_merchants_1h"] = float(rf.distinct_merchants_1h)
            feat_values["distinct_categories_1h"] = float(rf.distinct_categories_1h)
            feat_values["distinct_devices_15m"] = float(rf.distinct_devices_15m)
            feat_values["distinct_ips_15m"] = float(rf.distinct_ips_15m)
            feat_values["is_foreign_transaction"] = 1.0 if rf.is_foreign_transaction else 0.0
            feat_values["failed_auth_5m"] = float(rf.failed_auth_5m)
            feat_values["failed_auth_1h"] = float(rf.failed_auth_1h)
            feat_values["consecutive_failures"] = float(rf.consecutive_failures)
            feat_values["high_risk_flags_24h"] = float(rf.high_risk_flags_24h)
        elif isinstance(redis_features, dict):
            for k in [
                "velocity_1m", "velocity_5m", "velocity_15m", "velocity_1h", "velocity_24h",
                "rolling_amount_1h", "avg_amount_1h", "max_amount_1h", "rolling_amount_24h",
                "avg_amount_24h", "amount_deviation_ratio", "distinct_merchants_1h",
                "distinct_categories_1h", "distinct_devices_15m", "distinct_ips_15m",
                "is_foreign_transaction", "failed_auth_5m", "failed_auth_1h",
                "consecutive_failures", "high_risk_flags_24h"
            ]:
                feat_values[k] = float(redis_features.get(k, FEATURE_DEFAULT_MAP[k]))
        else:
            for k in [
                "velocity_1m", "velocity_5m", "velocity_15m", "velocity_1h", "velocity_24h",
                "rolling_amount_1h", "avg_amount_1h", "max_amount_1h", "rolling_amount_24h",
                "avg_amount_24h", "amount_deviation_ratio", "distinct_merchants_1h",
                "distinct_categories_1h", "distinct_devices_15m", "distinct_ips_15m",
                "is_foreign_transaction", "failed_auth_5m", "failed_auth_1h",
                "consecutive_failures", "high_risk_flags_24h"
            ]:
                feat_values[k] = FEATURE_DEFAULT_MAP[k]

        # Group 6: Neo4j Graph Relationship Features
        if isinstance(graph_features, GraphRiskFeatures):
            gf = graph_features
            feat_values["graph_shared_device_users"] = float(gf.shared_device_users_count)
            feat_values["graph_shared_ip_users"] = float(gf.shared_ip_users_count)
            feat_values["graph_shared_device_frauds"] = float(gf.device_fraud_history_count)
            feat_values["graph_shared_ip_frauds"] = float(gf.ip_fraud_history_count)
            feat_values["graph_fraud_ring_size"] = float(gf.fraud_ring_size)
            feat_values["graph_is_device_shared"] = 1.0 if gf.is_device_shared else 0.0
            feat_values["graph_is_ip_shared"] = 1.0 if gf.is_ip_shared else 0.0
            feat_values["graph_risk_score"] = float(gf.composite_graph_risk_score)
        elif isinstance(graph_features, dict):
            for k in [
                "graph_shared_device_users", "graph_shared_ip_users",
                "graph_shared_device_frauds", "graph_shared_ip_frauds",
                "graph_fraud_ring_size", "graph_is_device_shared",
                "graph_is_ip_shared", "graph_risk_score"
            ]:
                feat_values[k] = float(graph_features.get(k, FEATURE_DEFAULT_MAP[k]))
        else:
            for k in [
                "graph_shared_device_users", "graph_shared_ip_users",
                "graph_shared_device_frauds", "graph_shared_ip_frauds",
                "graph_fraud_ring_size", "graph_is_device_shared",
                "graph_is_ip_shared", "graph_risk_score"
            ]:
                feat_values[k] = FEATURE_DEFAULT_MAP[k]

        # Ensure all canonical features are present in order
        for name, default in FEATURE_DEFAULT_MAP.items():
            if name not in feat_values:
                feat_values[name] = default

        return UnifiedFeatureVector(
            features=feat_values,
            schema_version=cls.SCHEMA_VERSION,
            extracted_at=ts,
        )
