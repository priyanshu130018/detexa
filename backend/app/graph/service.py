"""
app/graph/service.py
─────────────────────────────────────────────────────────────────────────────
High-level Graph Service for fraud relationship analysis, entity resolution,
and fraud ring detection.
"""

from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger
from app.graph.models import (
    FraudRingCluster,
    GraphRiskFeatures,
    SubgraphVisualization,
)
from app.graph.repository import Neo4jGraphRepository


class Neo4jGraphService:
    """
    Business service encapsulating Neo4j graph operations with in-memory fallback.
    """

    def __init__(self, repo: Optional[Neo4jGraphRepository] = None):
        self.repo = repo or Neo4jGraphRepository()
        # Fallback local in-memory graph for offline / test environments
        self._fallback_device_users: Dict[str, set] = {}
        self._fallback_ip_users: Dict[str, set] = {}
        self._fallback_frauds: Dict[str, int] = {}

    def sync_transaction(
        self,
        user_id: str,
        transaction_ref: str,
        amount: float,
        currency: str = "INR",
        merchant_name: str = "Reliance Digital",
        merchant_category: str = "General",
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        country: str = "IN",
        fraud_score: float = 0.0,
        risk_level: str = "Low",
        decision: str = "ALLOW",
        is_fraud: bool = False,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Syncs a transaction into Neo4j graph and in-memory fallback."""
        # Update in-memory fallback
        if device_fingerprint:
            self._fallback_device_users.setdefault(device_fingerprint, set()).add(user_id)
            if is_fraud or risk_level == "High":
                self._fallback_frauds[device_fingerprint] = self._fallback_frauds.get(device_fingerprint, 0) + 1

        if ip_address and ip_address not in ("0.0.0.0", ""):
            self._fallback_ip_users.setdefault(ip_address, set()).add(user_id)
            if is_fraud or risk_level == "High":
                self._fallback_frauds[ip_address] = self._fallback_frauds.get(ip_address, 0) + 1

        # Sync to Neo4j if enabled
        if settings.neo4j_enabled:
            return self.repo.record_transaction_graph(
                user_id=user_id,
                transaction_ref=transaction_ref,
                amount=amount,
                currency=currency,
                merchant_name=merchant_name,
                merchant_category=merchant_category,
                device_fingerprint=device_fingerprint,
                ip_address=ip_address,
                country=country,
                fraud_score=fraud_score,
                risk_level=risk_level,
                decision=decision,
                is_fraud=is_fraud,
                timestamp=timestamp,
            )
        return True

    def get_features(
        self,
        user_id: str,
        current_device_fp: Optional[str] = None,
        current_ip: Optional[str] = None,
    ) -> GraphRiskFeatures:
        """Retrieves graph-based identity and network risk features."""
        if settings.neo4j_enabled:
            return self.repo.get_user_graph_features(
                user_id=user_id,
                current_device_fp=current_device_fp,
                current_ip=current_ip,
            )

        # Fallback evaluation
        dev_users = len(self._fallback_device_users.get(current_device_fp, set())) if current_device_fp else 1
        dev_users = max(dev_users, 1)
        ip_users = len(self._fallback_ip_users.get(current_ip, set())) if current_ip else 1
        ip_users = max(ip_users, 1)

        dev_frauds = self._fallback_frauds.get(current_device_fp, 0) if current_device_fp else 0
        ip_frauds = self._fallback_frauds.get(current_ip, 0) if current_ip else 0

        is_dev_shared = dev_users > 1
        is_ip_shared = ip_users > 1
        risk = min(1.0, (0.3 if is_dev_shared else 0.0) + (0.2 if is_ip_shared else 0.0) + (dev_frauds * 0.2) + (ip_frauds * 0.1))

        return GraphRiskFeatures(
            user_id=user_id,
            device_fingerprint=current_device_fp,
            ip_address=current_ip,
            shared_device_user_count=dev_users,
            shared_ip_user_count=ip_users,
            shared_device_fraud_count=dev_frauds,
            shared_ip_fraud_count=ip_frauds,
            is_device_shared=is_dev_shared,
            is_ip_shared=is_ip_shared,
            graph_risk_score=risk,
        )

    def get_fraud_rings(
        self,
        min_users: int = 2,
        limit: int = 20,
    ) -> List[FraudRingCluster]:
        """Discovers multi-user collusion fraud rings."""
        if settings.neo4j_enabled:
            return self.repo.detect_fraud_rings(min_users_per_device=min_users, limit=limit)

        # Fallback mock rings from memory
        mock_rings: List[FraudRingCluster] = []
        for i, (dev, users) in enumerate(self._fallback_device_users.items()):
            if len(users) >= min_users:
                fraud_cnt = self._fallback_frauds.get(dev, 0)
                mock_rings.append(
                    FraudRingCluster(
                        ring_id=f"RING-DEV-{i+1:03d}",
                        primary_entity_type="Device",
                        entity_key=dev,
                        associated_users=list(users),
                        user_count=len(users),
                        associated_transactions=[],
                        total_fraud_amount=0.0,
                        confirmed_fraud_count=fraud_cnt,
                        risk_level="High" if fraud_cnt > 0 else "Medium",
                        description=f"Device {dev[:8]} shared by {len(users)} users.",
                    )
                )
        return mock_rings[:limit]

    def get_subgraph(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 2,
    ) -> SubgraphVisualization:
        """Retrieves visualization subgraph nodes and links."""
        return self.repo.get_entity_subgraph(
            entity_type=entity_type,
            entity_id=entity_id,
            depth=depth,
        )

    def health(self) -> Dict[str, Any]:
        """Returns Neo4j health and connection status."""
        return self.repo.health_check()


_graph_service_instance: Optional[Neo4jGraphService] = None


def get_graph_service() -> Neo4jGraphService:
    """Returns singleton instance of Neo4jGraphService."""
    global _graph_service_instance
    if _graph_service_instance is None:
        _graph_service_instance = Neo4jGraphService()
    return _graph_service_instance
