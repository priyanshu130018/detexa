"""
app/features/schema.py
─────────────────────────────────────────────────────────────────────────────
Canonical Feature Schema Specification for Detexa Fraud Detection Platform.
Version: 4.0.0 (Indian Banking Transaction Fraud System)

Defines the exact, ordered feature vector shared across:
1. Model Training & Offline Feature Extraction (Indian Banking Transactions)
2. Batch CSV / Parquet Offline Inference
3. Real-Time Online Inference (FastAPI)
4. Distributed Stream Processing (Apache Flink / Kafka)

Prevents Training-Serving Skew by strictly enforcing feature ordering, data types,
and deterministic transformations.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

FEATURE_SCHEMA_VERSION = "4.0.0"


class FeatureGroup(str, Enum):
    TRANSACTION = "transaction"
    TEMPORAL = "temporal"
    BEHAVIORAL = "behavioral"
    CUSTOMER_HISTORY = "customer_history"
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


# ── Canonical Ordered Feature Definitions for Indian Banking Fraud Detection ──

CANONICAL_FEATURE_DEFINITIONS: List[FeatureDefinition] = [
    # ── Group 1: Transaction Monetary & Account Balance Features ─────────────
    FeatureDefinition("transaction_amount", FeatureGroup.TRANSACTION, "float", 0.0, "Transaction amount in INR (₹)"),
    FeatureDefinition("log_transaction_amount", FeatureGroup.TRANSACTION, "float", 0.0, "Log-transformed transaction amount ln(1 + Amount)"),
    FeatureDefinition("transaction_amount_sq", FeatureGroup.TRANSACTION, "float", 0.0, "Squared transaction amount Amount^2"),
    FeatureDefinition("account_balance", FeatureGroup.TRANSACTION, "float", 50000.0, "Customer account balance in INR (₹)"),
    FeatureDefinition("log_account_balance", FeatureGroup.TRANSACTION, "float", 10.82, "Log-transformed account balance ln(1 + Balance)"),
    FeatureDefinition("amount_to_balance_ratio", FeatureGroup.TRANSACTION, "float", 0.1, "Ratio of transaction amount to account balance"),
    FeatureDefinition("credit_score", FeatureGroup.TRANSACTION, "float", 650.0, "Customer credit bureau score [300 - 900]"),
    FeatureDefinition("has_loan", FeatureGroup.TRANSACTION, "float", 0.0, "Binary flag indicating active loan account"),
    FeatureDefinition("emi_amount", FeatureGroup.TRANSACTION, "float", 0.0, "Monthly Equated Monthly Installment in INR"),
    FeatureDefinition("log_emi_amount", FeatureGroup.TRANSACTION, "float", 0.0, "Log-transformed EMI amount ln(1 + EMI)"),
    FeatureDefinition("emi_to_balance_ratio", FeatureGroup.TRANSACTION, "float", 0.0, "Monthly EMI obligation relative to account balance"),
    FeatureDefinition("amount_to_emi_ratio", FeatureGroup.TRANSACTION, "float", 0.0, "Transaction amount relative to monthly EMI amount"),

    # ── Group 2: Temporal & Diurnal Features ─────────────────────────────────
    FeatureDefinition("transaction_hour", FeatureGroup.TEMPORAL, "float", 12.0, "Hour of transaction event in IST [0.0 - 23.99]"),
    FeatureDefinition("hour_sin", FeatureGroup.TEMPORAL, "float", 0.0, "Cyclical continuous encoding sin(2*pi*hour/24)"),
    FeatureDefinition("hour_cos", FeatureGroup.TEMPORAL, "float", 1.0, "Cyclical continuous encoding cos(2*pi*hour/24)"),
    FeatureDefinition("is_night_txn", FeatureGroup.TEMPORAL, "float", 0.0, "Binary flag for off-peak nocturnal hours (22:00 - 06:00 IST)"),

    # ── Group 3: Customer Historical & Velocity Features (Leakage-Free) ──────
    FeatureDefinition("cust_txn_count_prior", FeatureGroup.CUSTOMER_HISTORY, "float", 1.0, "Prior historical transaction count for this customer"),
    FeatureDefinition("cust_avg_amount_prior", FeatureGroup.CUSTOMER_HISTORY, "float", 25000.0, "Customer historical moving average transaction amount (₹)"),
    FeatureDefinition("cust_amount_diff_from_avg", FeatureGroup.CUSTOMER_HISTORY, "float", 0.0, "Deviation of current amount from customer historical mean (₹)"),
    FeatureDefinition("cust_amount_ratio_to_avg", FeatureGroup.CUSTOMER_HISTORY, "float", 1.0, "Ratio of current amount to customer historical mean"),
    FeatureDefinition("cust_time_since_last_txn_hours", FeatureGroup.CUSTOMER_HISTORY, "float", 24.0, "Hours elapsed since previous transaction by customer"),
    FeatureDefinition("cust_channel_change", FeatureGroup.CUSTOMER_HISTORY, "float", 0.0, "Binary flag for sudden customer channel switch"),
    FeatureDefinition("cust_type_change", FeatureGroup.CUSTOMER_HISTORY, "float", 0.0, "Binary flag for sudden customer transaction type switch"),

    # ── Group 4: Behavioral & Biometrics ─────────────────────────────────────
    FeatureDefinition("typing_speed", FeatureGroup.BEHAVIORAL, "float", 45.0, "Keystroke dynamic entry speed (chars/sec)"),
    FeatureDefinition("mouse_velocity", FeatureGroup.BEHAVIORAL, "float", 250.0, "Cursor pointer movement velocity (px/sec)"),
    FeatureDefinition("failed_logins", FeatureGroup.BEHAVIORAL, "float", 0.0, "Recent failed authentication attempts"),
    FeatureDefinition("is_vpn", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary flag for anonymizing VPN connection"),
    FeatureDefinition("is_tor", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary flag for Tor exit node traffic"),
    FeatureDefinition("device_change", FeatureGroup.BEHAVIORAL, "float", 0.0, "Binary indicator of sudden device switch"),
    FeatureDefinition("risk_combo", FeatureGroup.BEHAVIORAL, "float", 0.0, "Composite behavioral risk index (is_vpn + 2*is_tor + device_change)"),

    # ── Group 5: Redis Real-Time Sliding Windows ─────────────────────────────
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
    FeatureDefinition("consecutive_failures", FeatureGroup.REDIS_REALTIME, "float", 0.0, "Consecutive authentication / decline streak"),
    FeatureDefinition("high_risk_flags_24h", FeatureGroup.REDIS_REALTIME, "float", 0.0, "High-risk alerts triggered by user in last 24 hours"),

    # ── Group 6: Neo4j Graph Relationship Features ───────────────────────────
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
