"""
app/graph/models.py
─────────────────────────────────────────────────────────────────────────────
Data models and feature schemas for Neo4j fraud relationship analysis.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class GraphNode:
    """Graph node entity representation."""
    id: str
    label: str  # User, Device, IPAddress, Merchant, Transaction
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Graph relationship entity representation."""
    source: str
    target: str
    type: str  # USES_DEVICE, USES_IP, TRANSACTED_WITH, PERFORMED, ORIGINATED_FROM
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphRiskFeatures:
    """
    Graph-derived features quantifying identity sharing, network risk, and entity linkage.
    """
    user_id: str
    device_fingerprint: Optional[str] = None
    ip_address: Optional[str] = None
    shared_device_user_count: int = 1
    shared_ip_user_count: int = 1
    shared_device_fraud_count: int = 0
    shared_ip_fraud_count: int = 0
    associated_merchant_count: int = 1
    fraud_ring_size: int = 1
    suspicious_neighbors_count: int = 0
    is_device_shared: bool = False
    is_ip_shared: bool = False
    graph_risk_score: float = 0.0  # Normalized [0.0, 1.0]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "device_fingerprint": self.device_fingerprint,
            "ip_address": self.ip_address,
            "shared_device_user_count": self.shared_device_user_count,
            "shared_ip_user_count": self.shared_ip_user_count,
            "shared_device_fraud_count": self.shared_device_fraud_count,
            "shared_ip_fraud_count": self.shared_ip_fraud_count,
            "associated_merchant_count": self.associated_merchant_count,
            "fraud_ring_size": self.fraud_ring_size,
            "suspicious_neighbors_count": self.suspicious_neighbors_count,
            "is_device_shared": self.is_device_shared,
            "is_ip_shared": self.is_ip_shared,
            "graph_risk_score": round(self.graph_risk_score, 4),
        }

    def to_ml_features(self) -> Dict[str, float]:
        """Convert graph features to float values for ML model inference."""
        return {
            "graph_shared_device_users": float(self.shared_device_user_count),
            "graph_shared_ip_users": float(self.shared_ip_user_count),
            "graph_shared_device_frauds": float(self.shared_device_fraud_count),
            "graph_shared_ip_frauds": float(self.shared_ip_fraud_count),
            "graph_fraud_ring_size": float(self.fraud_ring_size),
            "graph_risk_score": float(self.graph_risk_score),
            "graph_is_device_shared": 1.0 if self.is_device_shared else 0.0,
            "graph_is_ip_shared": 1.0 if self.is_ip_shared else 0.0,
        }


@dataclass
class FraudRingCluster:
    """Identified cluster of suspicious entities sharing devices or IPs."""
    ring_id: str
    primary_entity_type: str  # Device or IPAddress
    entity_key: str
    associated_users: List[str]
    user_count: int
    associated_transactions: List[str]
    total_fraud_amount: float
    confirmed_fraud_count: int
    risk_level: str
    description: str


@dataclass
class SubgraphVisualization:
    """Graph payload formatted for D3/Cytoscape frontend visualization."""
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    root_id: str
    entity_type: str
    depth: int
