"""
app/services/graph_service.py
─────────────────────────────────────────────────────────────────────────────
Service layer adapter for the Neo4j Graph Subsystem.
Enables dependency injection in FastAPI route handlers.
"""

from typing import Any, Dict, List, Optional
from app.graph import (
    FraudRingCluster,
    GraphRiskFeatures,
    Neo4jGraphService,
    SubgraphVisualization,
    get_graph_service,
)


class GraphService:
    """FastAPI Service dependency wrapper around the Neo4j Graph Service."""

    def __init__(self, service: Optional[Neo4jGraphService] = None):
        self.service = service or get_graph_service()

    def sync_transaction(
        self,
        user_id: str,
        transaction_ref: str,
        amount: float,
        currency: str = "USD",
        merchant_name: str = "Online Merchant",
        merchant_category: str = "General",
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        country: str = "US",
        fraud_score: float = 0.0,
        risk_level: str = "Low",
        decision: str = "ALLOW",
        is_fraud: bool = False,
    ) -> bool:
        return self.service.sync_transaction(
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
        )

    def get_features(
        self,
        user_id: str,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> GraphRiskFeatures:
        return self.service.get_features(
            user_id=user_id,
            current_device_fp=device_fingerprint,
            current_ip=ip_address,
        )

    def list_fraud_rings(
        self,
        min_users: int = 2,
        limit: int = 20,
    ) -> List[FraudRingCluster]:
        return self.service.get_fraud_rings(min_users=min_users, limit=limit)

    def get_subgraph(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 2,
    ) -> SubgraphVisualization:
        return self.service.get_subgraph(
            entity_type=entity_type,
            entity_id=entity_id,
            depth=depth,
        )

    def health(self) -> Dict[str, Any]:
        return self.service.health()
