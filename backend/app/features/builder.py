"""
app/features/builder.py
─────────────────────────────────────────────────────────────────────────────
Unified Fraud Feature Builder for Detexa Platform.

Provides a single, authoritative feature extraction engine shared across:
- Model Training (preventing data leakage and feature skew)
- Batch Offline Inference
- Online Real-Time Inference (FastAPI)
- Streaming Window Ingestion (Apache Flink)

Combines:
1. Core Transaction & PCA Dimensions
2. Diurnal & Temporal Cyclical Encodings
3. Behavioral & Biometric Signals
4. Redis Real-Time Sliding Windows
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
        Builds a canonical unified feature vector from raw payload + optional Redis and Graph sources.
        """
        ts = timestamp or float(payload.get("timestamp", time.time()))
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        hour = float(payload.get("hour_of_day", dt.hour + dt.minute / 60.0))

        feat_values: Dict[str, float] = {}

        # ── 1. Core Transaction & Amount Features ────────────────────────────
        amount = float(payload.get("amount", payload.get("Amount", 0.0)))
        feat_values["amount"] = amount
        feat_values["log_amount"] = float(np.log1p(max(amount, 0.0)))
        feat_values["amount_sq"] = float(amount ** 2)

        # Extract PCA components v1 .. v28
        pca_sq_sum = 0.0
        v_dict: Dict[str, float] = {}
        for i in range(1, 29):
            col_k = f"v{i}"
            val = float(payload.get(col_k, payload.get(col_k.upper(), 0.0)))
            v_dict[col_k] = val
            feat_values[col_k] = val
            pca_sq_sum += val ** 2

        feat_values["v_norm"] = float(np.sqrt(pca_sq_sum))

        # Interaction terms
        feat_values["v1_v2_interaction"] = v_dict.get("v1", 0.0) * v_dict.get("v2", 0.0)
        feat_values["v3_v7_interaction"] = v_dict.get("v3", 0.0) * v_dict.get("v7", 0.0)
        feat_values["v4_v11_interaction"] = v_dict.get("v4", 0.0) * v_dict.get("v11", 0.0)
        feat_values["v12_v10_interaction"] = v_dict.get("v12", 0.0) * v_dict.get("v10", 0.0)
        feat_values["v14_v12_interaction"] = v_dict.get("v14", 0.0) * v_dict.get("v12", 0.0)
        feat_values["v14_v17_interaction"] = v_dict.get("v14", 0.0) * v_dict.get("v17", 0.0)
        feat_values["v17_v12_interaction"] = v_dict.get("v17", 0.0) * v_dict.get("v12", 0.0)

        # ── 2. Temporal & Diurnal Encodings ──────────────────────────────────
        feat_values["hour_of_day"] = hour
        feat_values["sin_time"] = float(np.sin(2.0 * np.pi * hour / 24.0))
        feat_values["cos_time"] = float(np.cos(2.0 * np.pi * hour / 24.0))
        feat_values["is_night_txn"] = 1.0 if (hour < 6.0 or hour >= 22.0) else 0.0

        # ── 3. Behavioral & Biometrics ───────────────────────────────────────
        typing_spd = float(payload.get("typing_speed", 45.0))
        mouse_vel = float(payload.get("mouse_velocity", 250.0))
        failed_lg = float(payload.get("failed_logins", 0.0))
        is_vpn = float(bool(payload.get("is_vpn", False)))
        is_tor = float(bool(payload.get("is_tor", False)))
        dev_change = float(bool(payload.get("device_change", payload.get("device_changed", False))))

        feat_values["typing_speed"] = typing_spd
        feat_values["mouse_velocity"] = mouse_vel
        feat_values["failed_logins"] = failed_lg
        feat_values["is_vpn"] = is_vpn
        feat_values["is_tor"] = is_tor
        feat_values["device_change"] = dev_change
        feat_values["risk_combo"] = is_vpn + (2.0 * is_tor) + dev_change

        # ── 4. Redis Real-Time Sliding Windows ───────────────────────────────
        if isinstance(redis_features, HotFeatureVector):
            rf_dict = redis_features.to_ml_features()
        elif isinstance(redis_features, dict):
            rf_dict = redis_features
        else:
            rf_dict = {}

        feat_values["velocity_1m"] = float(rf_dict.get("velocity_1m", payload.get("velocity_1m", 1.0)))
        feat_values["velocity_5m"] = float(rf_dict.get("velocity_5m", payload.get("velocity_5m", 1.0)))
        feat_values["velocity_15m"] = float(rf_dict.get("velocity_15m", payload.get("velocity_15m", 1.0)))
        feat_values["velocity_1h"] = float(rf_dict.get("velocity_1h", payload.get("velocity_1h", 1.0)))
        feat_values["velocity_24h"] = float(rf_dict.get("velocity_24h", payload.get("velocity_24h", 1.0)))
        feat_values["rolling_amount_1h"] = float(rf_dict.get("rolling_amount_1h", payload.get("rolling_amount_1h", amount)))
        feat_values["avg_amount_1h"] = float(rf_dict.get("avg_amount_1h", payload.get("avg_amount_1h", amount)))
        feat_values["max_amount_1h"] = float(rf_dict.get("max_amount_1h", payload.get("max_amount_1h", amount)))
        feat_values["rolling_amount_24h"] = float(rf_dict.get("rolling_amount_24h", payload.get("rolling_amount_24h", amount)))
        feat_values["avg_amount_24h"] = float(rf_dict.get("avg_amount_24h", payload.get("avg_amount_24h", amount)))
        feat_values["amount_deviation_ratio"] = float(rf_dict.get("amount_deviation_ratio", payload.get("amount_deviation_ratio", 1.0)))
        feat_values["distinct_merchants_1h"] = float(rf_dict.get("distinct_merchants_1h", payload.get("distinct_merchants_1h", 1.0)))
        feat_values["distinct_categories_1h"] = float(rf_dict.get("distinct_categories_1h", payload.get("distinct_categories_1h", 1.0)))
        feat_values["distinct_devices_15m"] = float(rf_dict.get("distinct_devices_15m", payload.get("distinct_devices_15m", 1.0)))
        feat_values["distinct_ips_15m"] = float(rf_dict.get("distinct_ips_15m", payload.get("distinct_ips_15m", 1.0)))
        feat_values["is_foreign_transaction"] = float(bool(rf_dict.get("is_foreign_transaction", payload.get("is_foreign_transaction", False))))
        feat_values["failed_auth_5m"] = float(rf_dict.get("failed_auth_5m", payload.get("failed_auth_5m", 0.0)))
        feat_values["failed_auth_1h"] = float(rf_dict.get("failed_auth_1h", payload.get("failed_auth_1h", 0.0)))
        feat_values["consecutive_failures"] = float(rf_dict.get("consecutive_failures", payload.get("consecutive_failures", 0.0)))
        feat_values["high_risk_flags_24h"] = float(rf_dict.get("high_risk_flags_24h", payload.get("high_risk_flags_24h", 0.0)))

        # ── 5. Neo4j Graph Relationship Features ─────────────────────────────
        if isinstance(graph_features, GraphRiskFeatures):
            gf_dict = graph_features.to_ml_features()
        elif isinstance(graph_features, dict):
            gf_dict = graph_features
        else:
            gf_dict = {}

        feat_values["graph_shared_device_users"] = float(gf_dict.get("graph_shared_device_users", payload.get("graph_shared_device_users", 1.0)))
        feat_values["graph_shared_ip_users"] = float(gf_dict.get("graph_shared_ip_users", payload.get("graph_shared_ip_users", 1.0)))
        feat_values["graph_shared_device_frauds"] = float(gf_dict.get("graph_shared_device_frauds", payload.get("graph_shared_device_frauds", 0.0)))
        feat_values["graph_shared_ip_frauds"] = float(gf_dict.get("graph_shared_ip_frauds", payload.get("graph_shared_ip_frauds", 0.0)))
        feat_values["graph_fraud_ring_size"] = float(gf_dict.get("graph_fraud_ring_size", payload.get("graph_fraud_ring_size", 1.0)))
        feat_values["graph_is_device_shared"] = float(bool(gf_dict.get("graph_is_device_shared", payload.get("graph_is_device_shared", False))))
        feat_values["graph_is_ip_shared"] = float(bool(gf_dict.get("graph_is_ip_shared", payload.get("graph_is_ip_shared", False))))
        feat_values["graph_risk_score"] = float(gf_dict.get("graph_risk_score", payload.get("graph_risk_score", 0.0)))

        # Apply any default imputations for missing keys
        for k, default_v in FEATURE_DEFAULT_MAP.items():
            if k not in feat_values or np.isnan(feat_values[k]):
                feat_values[k] = default_v

        user_id_str = str(payload.get("user_id", "")) if payload.get("user_id") else None
        txn_ref_str = str(payload.get("transaction_ref", payload.get("ref", ""))) if payload.get("transaction_ref") or payload.get("ref") else None

        return UnifiedFeatureVector(
            values=feat_values,
            schema_version=cls.SCHEMA_VERSION,
            user_id=user_id_str,
            transaction_ref=txn_ref_str,
            timestamp=ts,
            raw_context=payload,
        )

    @classmethod
    def build_batch_dataframe(cls, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Builds a unified DataFrame strictly adhering to canonical feature names and column order.
        """
        vectors = [cls.build_realtime_vector(rec) for rec in records]
        rows = [v.to_dict() for v in vectors]
        return pd.DataFrame(rows, columns=CANONICAL_FEATURE_NAMES)

    @classmethod
    def build_training_dataframe(cls, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms raw historical DataFrame (e.g. Kaggle Credit dataset) into the exact canonical schema.
        Prevents feature mismatch during offline training.
        """
        df = df_raw.copy()
        col_map = {c: c.lower() for c in df.columns}
        df.rename(columns=col_map, inplace=True)

        records = df.to_dict(orient="records")
        return cls.build_batch_dataframe(records)

    @classmethod
    def get_schema_metadata(cls) -> Dict[str, Any]:
        """
        Exports full feature schema metadata including definitions, groups, and versions.
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in CANONICAL_FEATURE_DEFINITIONS:
            g_name = f.group.value
            if g_name not in groups:
                groups[g_name] = []
            groups[g_name].append({
                "name": f.name,
                "dtype": f.dtype,
                "default": f.default_value,
                "description": f.description,
            })

        return {
            "schema_version": cls.SCHEMA_VERSION,
            "total_feature_count": len(CANONICAL_FEATURE_NAMES),
            "feature_names": CANONICAL_FEATURE_NAMES,
            "feature_groups": groups,
            "group_counts": {k: len(v) for k, v in groups.items()},
        }
