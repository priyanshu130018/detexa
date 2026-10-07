"""
app/api/v1/endpoints/graph.py
─────────────────────────────────────────────────────────────────────────────
REST endpoints for Neo4j fraud relationship analysis, graph risk scoring,
fraud ring exploration, and subgraph visualizations.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.db.models import User
from app.graph import (
    FraudRingCluster,
    GraphRiskFeatures,
    Neo4jGraphService,
    SubgraphVisualization,
    get_graph_service,
)

router = APIRouter()


def get_graph_service_dep() -> Neo4jGraphService:
    return get_graph_service()


@router.get(
    "/features/{user_id}",
    summary="Get graph-derived risk features",
    description="Calculates identity sharing risk (shared devices, shared IPs, 2-hop fraud density, and graph risk score).",
)
def get_user_graph_features(
    user_id: str,
    device_fingerprint: Optional[str] = Query(None, description="Current device fingerprint to test"),
    ip_address: Optional[str] = Query(None, description="Current IP address to test"),
    service: Neo4jGraphService = Depends(get_graph_service_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    features: GraphRiskFeatures = service.get_features(
        user_id=user_id,
        current_device_fp=device_fingerprint,
        current_ip=ip_address,
    )
    return {
        "user_id": user_id,
        "graph_features": features.to_dict(),
        "ml_features": features.to_ml_features(),
    }


@router.get(
    "/fraud-rings",
    summary="Detect shared entity fraud rings",
    description="Finds clusters of users sharing the same hardware devices or IP addresses with suspicious fraud activity.",
)
def list_fraud_rings(
    min_users: int = Query(2, ge=2, description="Minimum distinct users sharing an entity"),
    limit: int = Query(20, ge=1, le=100, description="Max rings to return"),
    service: Neo4jGraphService = Depends(get_graph_service_dep),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    rings: List[FraudRingCluster] = service.get_fraud_rings(min_users=min_users, limit=limit)
    return [
        {
            "ring_id": r.ring_id,
            "entity_type": r.primary_entity_type,
            "entity_key": r.entity_key,
            "user_count": r.user_count,
            "associated_users": r.associated_users,
            "associated_transactions": r.associated_transactions,
            "confirmed_fraud_count": r.confirmed_fraud_count,
            "total_fraud_amount": r.total_fraud_amount,
            "risk_level": r.risk_level,
            "description": r.description,
        }
        for r in rings
    ]


@router.get(
    "/subgraph/{entity_type}/{entity_id}",
    summary="Get multi-hop subgraph for visualization",
    description="Extracts visual graph nodes and edges up to N hops around an entity (User, Device, IPAddress, Merchant, Transaction).",
)
def get_entity_subgraph(
    entity_type: str,
    entity_id: str,
    depth: int = Query(2, ge=1, le=3, description="Graph traversal depth"),
    service: Neo4jGraphService = Depends(get_graph_service_dep),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    # Normalize entity type capitalization
    valid_labels = {"User": "User", "Device": "Device", "IPAddress": "IPAddress", "ipaddress": "IPAddress", "Merchant": "Merchant", "Transaction": "Transaction"}
    normalized_label = valid_labels.get(entity_type.capitalize(), entity_type)

    subgraph: SubgraphVisualization = service.get_subgraph(
        entity_type=normalized_label,
        entity_id=entity_id,
        depth=depth,
    )
    return {
        "root_id": subgraph.root_id,
        "entity_type": subgraph.entity_type,
        "depth": subgraph.depth,
        "nodes": subgraph.nodes,
        "edges": subgraph.edges,
    }


@router.get(
    "/health",
    summary="Neo4j Graph Database health status",
    description="Checks connection status, query latency, and node counts in Neo4j.",
)
def get_graph_health(
    service: Neo4jGraphService = Depends(get_graph_service_dep),
) -> Dict[str, Any]:
    return service.health()
