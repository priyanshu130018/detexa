"""
app/features/schema.py
─────────────────────────────────────────────────────────────────────────────
Canonical Feature Schema Specification for Detexa Fraud Detection Platform.
Version: 3.0.0

Defines the exact, ordered feature vector shared across:
1. Model Training & Offline Feature Extraction
2. Batch CSV / Parquet Offline Inference
3. Real-Time Online Inference (FastAPI)
4. Distributed Stream Processing (Apache Flink / Kafka)

Prevents Training-Serving Skew by strictly enforcing feature ordering, data types,
and deterministic transformations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

FEATURE_SCHEMA_VERSION = "3.0.0"


class FeatureGroup(str, Enum):
    TRANSACTION = "transaction"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    REDIS_REALTIME = "redis_realtime"
    GRAPH_RELATIONSHIP = "graph_relationship"


@dataclass(frozen=True)
class FeatureDefinition:
    """Metadata specification for an individual feature."""
    name: str
    group: FeatureGroup
    dtype: str
    default_value: float
    description: str


# ── Canonical Ordered Feature Definitions ────────────────────────────────────

CANONICAL_FEATURE_DEFINITIONS: List[FeatureDefinition] = [
    # ── Group 1: Transaction & PCA Components ────────────────────────────────
    FeatureDefinition("amount", FeatureGroup.TRANSACTION, "float", 0.0, "Transaction amount in base currency ($)"),
    FeatureDefinition("log_amount", FeatureGroup.TRANSACTION, "float", 0.0, "Log-transformed transaction amount ln(1 + Amount)"),
    FeatureDefinition("amount_sq", FeatureGroup.TRANSACTION, "float", 0.0, "Squared transaction amount Amount^2"),
    FeatureDefinition("v_norm", FeatureGroup.TRANSACTION, "float", 0.0, "L2 Euclidean norm across all 28 PCA components"),
    *(
        FeatureDefinition(f"v{i}", FeatureGroup.TRANSACTION, "float", 0.0, f"PCA dimension component V{i}")
        for i in range(1, 29)
    ),
    FeatureDefinition("v1_v2_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V1 * V2"),
    FeatureDefinition("v3_v7_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V3 * V7"),
    FeatureDefinition("v4_v11_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V4 * V11"),
    FeatureDefinition("v12_v10_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V12 * V10"),
    FeatureDefinition("v14_v12_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V14 * V12 (Top predictive driver)"),
    FeatureDefinition("v14_v17_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V14 * V17"),
    FeatureDefinition("v17_v12_interaction", FeatureGroup.TRANSACTION, "float", 0.0, "Interaction feature V17 * V12"),

    # ── Group 2: Temporal & Diurnal Features ─────────────────────────────────
    FeatureDefinition("hour_of_day", FeatureGroup.TEMPORAL, "float", 12.0, "Hour of transaction event in UTC [0.0 - 23.99]"),
    FeatureDefinition("sin_time", FeatureGroup.TEMPORAL, "float", 0.0, "Cyclical continuous encoding sin(2*pi*hour/24)"),
    FeatureDefinition("cos_time", FeatureGroup.TEMPORAL, "float", 1.0, "Cyclical continuous encoding cos(2*pi*hour/24)"),
    FeatureDefinition("is_night_txn", FeatureGroup.TEMPORAL, "float", 0.0, "Binary flag for off-peak nocturnal hours (00:00 - 06:00)"),

    # ── Group 3: Behavioral & Biometrics ─────────────────────────────────────
    FeatureDefinition("typing_speed", FeatureGroup.BEHAVIORAL, "float", 45.0, "Keystroke dynamic entry speed (chars/sec)"),
    FeatureDefinition("mouse_velocity", FeatureGroup.BEHAVIORAL, "float", 250.0, "Cursor pointer movement velocity (px/sec)"),
    FeatureDefinition("failed_logins", FeatureGroup.BEHAVIORAL, "float", 0.0, "Recent failed authentication attempts"),
    FeatureDefinition("is_vpn", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary flag for anonymizing VPN connection"),
    FeatureDefinition("is_tor", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary flag for Tor exit node traffic"),
    FeatureDefinition("device_change", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary indicator of sudden device switch"),
    FeatureDefinition("risk_combo", FeatureGroup.BEHAVIORAL, "float", 0.0, "Composite behavioral risk index (is_vpn + 2*is_tor + device_change)"),

    # ── Group 4: Redis Real-Time Sliding Windows ─────────────────────────────
    FeatureDefinition("velocity_1m", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Rolling transaction count in the last 1 minute"),
    FeatureDefinition("velocity_5m", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Rolling transaction count in the last 5 minutes"),
    FeatureDefinition("velocity_15m", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Rolling transaction count in the last 15 minutes"),
    FeatureDefinition("velocity_1h", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Rolling transaction count in the last 1 hour"),
    FeatureDefinition("velocity_24h", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Cumulative transaction count in the last 24 hours"),
    FeatureDefinition("rolling_amount_1h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Cumulative monetary amount spent in the last 1 hour"),
    FeatureDefinition("avg_amount_1h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Moving average transaction amount in the last 1 hour"),
    FeatureDefinition("max_amount_1h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Maximum single transaction amount in the last 1 hour"),
    FeatureDefinition("rolling_amount_24h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Cumulative monetary amount spent in the last 24 hours"),
    FeatureDefinition("avg_amount_24h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Moving average transaction amount in the last 24 hours"),
    FeatureDefinition("amount_deviation_ratio", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Current amount divided by 1-hour historical moving average"),
    FeatureDefinition("distinct_merchants_1h", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Distinct merchant destinations visited in 1 hour"),
    FeatureDefinition("distinct_categories_1h", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Distinct merchant categories transacted with in 1 hour"),
    FeatureDefinition("distinct_devices_15m", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Distinct hardware devices used in the last 15 minutes"),
    FeatureDefinition("distinct_ips_15m", FeatureGroup.REDIS_REALTIME, "float", 1.0, "Distinct IP addresses routed through in 15 minutes"),
    FeatureDefinition("is_foreign_transaction", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Flag indicating cross-border international transaction"),
    FeatureDefinition("failed_auth_5m", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Failed authorization attempts in the last 5 minutes"),
    FeatureDefinition("failed_auth_1h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Failed authorization attempts in the last 1 hour"),
    FeatureDefinition("consecutive_failures", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Consecutive authentication / card decline streak"),
    FeatureDefinition("high_risk_flags_24h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "High-risk alerts triggered by user in last 24 hours"),

    # ── Group 5: Neo4j Graph Relationship Features ───────────────────────────
    FeatureDefinition("graph_shared_device_users", FeatureGroup.GRAPH_RELATIONSHIP, "float", 1.0, "Distinct user accounts linked to this hardware device"),
    FeatureDefinition("graph_shared_ip_users", FeatureGroup.GRAPH_RELATIONSHIP, "float", 1.0, "Distinct user accounts sharing this IP address"),
    FeatureDefinition("graph_shared_device_frauds", FeatureGroup.GRAPH_RELATIONSHIP, "float", 0.0, "Confirmed fraudulent transactions from this hardware device"),
    FeatureDefinition("graph_shared_ip_frauds", FeatureGroup.GRAPH_RELATIONSHIP, "float", 0.0, "Confirmed fraudulent transactions originating from this IP"),
    FeatureDefinition("graph_fraud_ring_size", FeatureGroup.GRAPH_RELATIONSHIP, "float", 1.0, "Total interconnected nodes in the user's 2-hop graph neighborhood"),
    FeatureDefinition("graph_is_device_shared", FeatureGroup.GRAPH_RELATIONSHIP, "float", 0.0, "Binary indicator of multi-user hardware sharing"),
    FeatureDefinition("graph_is_ip_shared", FeatureGroup.GRAPH_RELATIONSHIP, "float", 0.0, "Binary indicator of multi-user IP address sharing"),
    FeatureDefinition("graph_risk_score", FeatureGroup.GRAPH_RELATIONSHIP, "float", 0.0, "Graph topological risk score [0.0 - 1.0]"),
]

# Canonical ordered list of column names for DataFrame / Numpy alignment
CANONICAL_FEATURE_NAMES: List[str] = [f.name for f in CANONICAL_FEATURE_DEFINITIONS]

# Fast lookup map for default values
FEATURE_DEFAULT_MAP: Dict[str, float] = {f.name: f.default_value for f in CANONICAL_FEATURE_DEFINITIONS}

# Total feature count
TOTAL_FEATURE_COUNT: int = len(CANONICAL_FEATURE_NAMES)
