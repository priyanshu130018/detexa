"""
app/graph/repository.py
─────────────────────────────────────────────────────────────────────────────
Cypher query repository for Neo4j graph operations and risk analysis.
Executes ACID graph transactions for entity resolution, link analysis, and fraud rings.
"""

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.core.neo4j import get_neo4j_driver
from app.graph.models import (
    FraudRingCluster,
    GraphEdge,
    GraphNode,
    GraphRiskFeatures,
    SubgraphVisualization,
)


class Neo4jGraphRepository:
    """
    Cypher Query Execution Repository for Detexa Fraud Graph.
    """

    def __init__(self):
        self._schema_initialized = False

    def init_schema(self) -> bool:
        """Creates unique constraints and indexes across all entity nodes."""
        driver = get_neo4j_driver()
        if driver is None:
            return False

        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Device) REQUIRE d.fingerprint IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ip:IPAddress) REQUIRE ip.address IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Merchant) REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Transaction) REQUIRE t.ref IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.timestamp)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Transaction) ON (t.is_fraud)",
        ]

        try:
            with driver.session() as session:
                for c in constraints:
                    session.run(c)
            self._schema_initialized = True
            logger.info("Successfully verified and applied Neo4j schema constraints.")
            return True
        except Exception as exc:
            logger.warning(f"Failed to initialize Neo4j schema constraints: {exc}")
            return False

    def record_transaction_graph(
        self,
        user_id: str,
        transaction_ref: str,
        amount: float,
        currency: str = "INR",
        merchant_name: str = "Reliance Digital",
        merchant_category: str = "Electronics",
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        country: str = "IN",
        fraud_score: float = 0.0,
        risk_level: str = "Low",
        decision: str = "ALLOW",
        is_fraud: bool = False,
        timestamp: Optional[float] = None,
    ) -> bool:
        """
        Creates/merges nodes and relationships for a transaction event in a single Cypher transaction.
        """
        driver = get_neo4j_driver()
        if driver is None:
            return False

        if not self._schema_initialized:
            self.init_schema()

        ts = timestamp or time.time()
        cypher = """
        MERGE (u:User {id: $user_id})
          ON CREATE SET u.created_at = $ts, u.risk_score = $fraud_score
          ON MATCH SET u.last_seen = $ts

        MERGE (m:Merchant {name: $merchant_name})
          ON CREATE SET m.category = $merchant_category, m.created_at = $ts

        MERGE (u)-[um:TRANSACTED_WITH]->(m)
          ON CREATE SET um.first_transacted = $ts, um.count = 1, um.total_amount = $amount
          ON MATCH SET um.last_transacted = $ts, um.count = um.count + 1, um.total_amount = um.total_amount + $amount

        MERGE (t:Transaction {ref: $txn_ref})
          SET t.amount = $amount,
              t.currency = $currency,
              t.fraud_score = $fraud_score,
              t.risk_level = $risk_level,
              t.decision = $decision,
              t.is_fraud = $is_fraud,
              t.timestamp = $ts,
              t.country = $country

        MERGE (u)-[:PERFORMED]->(t)
        MERGE (t)-[:TRANSACTED_AT]->(m)

        WITH u, t, m
        FOREACH (_ IN CASE WHEN $device_fp IS NOT NULL AND $device_fp <> '' THEN [1] ELSE [] END |
            MERGE (d:Device {fingerprint: $device_fp})
              ON CREATE SET d.first_seen = $ts, d.is_trusted = true
              ON MATCH SET d.last_seen = $ts
            MERGE (u)-[ud:USES_DEVICE]->(d)
              ON CREATE SET ud.first_used = $ts, ud.count = 1
              ON MATCH SET ud.last_used = $ts, ud.count = ud.count + 1
            MERGE (t)-[:ORIGINATED_FROM_DEVICE]->(d)
        )

        FOREACH (_ IN CASE WHEN $ip_addr IS NOT NULL AND $ip_addr <> '' AND $ip_addr <> '0.0.0.0' THEN [1] ELSE [] END |
            MERGE (ip:IPAddress {address: $ip_addr})
              ON CREATE SET ip.country = $country, ip.first_seen = $ts
              ON MATCH SET ip.last_seen = $ts
            MERGE (u)-[ui:USES_IP]->(ip)
              ON CREATE SET ui.first_used = $ts, ui.count = 1
              ON MATCH SET ui.last_used = $ts, ui.count = ui.count + 1
            MERGE (t)-[:ORIGINATED_FROM_IP]->(ip)
        )
        """

        params = {
            "user_id": str(user_id),
            "txn_ref": str(transaction_ref),
            "amount": float(amount),
            "currency": str(currency),
            "merchant_name": str(merchant_name),
            "merchant_category": str(merchant_category),
            "device_fp": device_fingerprint,
            "ip_addr": ip_address,
            "country": str(country),
            "fraud_score": float(fraud_score),
            "risk_level": str(risk_level),
            "decision": str(decision),
            "is_fraud": bool(is_fraud),
            "ts": float(ts),
        }

        try:
            with driver.session() as session:
                session.run(cypher, params)
            return True
        except Exception as exc:
            logger.warning(f"Neo4j record_transaction error for {transaction_ref}: {exc}")
            return False

    def get_user_graph_features(
        self,
        user_id: str,
        current_device_fp: Optional[str] = None,
        current_ip: Optional[str] = None,
    ) -> GraphRiskFeatures:
        """
        Runs graph traversal queries to extract shared-device and shared-IP risk metrics for a user.
        """
        driver = get_neo4j_driver()
        if driver is None:
            return GraphRiskFeatures(
                user_id=user_id,
                device_fingerprint=current_device_fp,
                ip_address=current_ip,
            )

        cypher = """
        MATCH (u:User {id: $user_id})

        // 1. Device sharing & fraud count
        OPTIONAL MATCH (u)-[:USES_DEVICE]->(d:Device)
        OPTIONAL MATCH (d)<-[:USES_DEVICE]-(other_dev_u:User)
        OPTIONAL MATCH (d)<-[:ORIGINATED_FROM_DEVICE]-(dev_t:Transaction WHERE dev_t.is_fraud = true)

        // 2. IP sharing & fraud count
        OPTIONAL MATCH (u)-[:USES_IP]->(ip:IPAddress)
        OPTIONAL MATCH (ip)<-[:USES_IP]-(other_ip_u:User)
        OPTIONAL MATCH (ip)<-[:ORIGINATED_FROM_IP]-(ip_t:Transaction WHERE ip_t.is_fraud = true)

        // 3. Merchant connectivity
        OPTIONAL MATCH (u)-[:TRANSACTED_WITH]->(m:Merchant)

        RETURN
            count(DISTINCT other_dev_u) AS shared_device_users,
            count(DISTINCT dev_t) AS device_fraud_txns,
            count(DISTINCT other_ip_u) AS shared_ip_users,
            count(DISTINCT ip_t) AS ip_fraud_txns,
            count(DISTINCT m) AS merchant_count
        """

        try:
            with driver.session() as session:
                res = session.run(cypher, {"user_id": str(user_id)}).single()
                if not res or res["shared_device_users"] is None:
                    # Check current device / ip specifically if user node is new
                    return self._inspect_transient_entities(user_id, current_device_fp, current_ip)

                dev_users = max(int(res["shared_device_users"] or 1), 1)
                ip_users = max(int(res["shared_ip_users"] or 1), 1)
                dev_frauds = int(res["device_fraud_txns"] or 0)
                ip_frauds = int(res["ip_fraud_txns"] or 0)
                merchants = max(int(res["merchant_count"] or 1), 1)

                is_dev_shared = dev_users > 1
                is_ip_shared = ip_users > 1

                # Calculate composite graph risk score [0.0 - 1.0]
                risk_score = 0.0
                if dev_users >= 3:
                    risk_score += 0.4
                elif dev_users >= 2:
                    risk_score += 0.2

                if ip_users >= 5:
                    risk_score += 0.3
                elif ip_users >= 3:
                    risk_score += 0.15

                if dev_frauds > 0:
                    risk_score += min(0.4, dev_frauds * 0.2)
                if ip_frauds > 0:
                    risk_score += min(0.3, ip_frauds * 0.15)

                risk_score = min(1.0, risk_score)

                return GraphRiskFeatures(
                    user_id=user_id,
                    device_fingerprint=current_device_fp,
                    ip_address=current_ip,
                    shared_device_user_count=dev_users,
                    shared_ip_user_count=ip_users,
                    shared_device_fraud_count=dev_frauds,
                    shared_ip_fraud_count=ip_frauds,
                    associated_merchant_count=merchants,
                    fraud_ring_size=max(dev_users + ip_users - 1, 1),
                    suspicious_neighbors_count=dev_frauds + ip_frauds,
                    is_device_shared=is_dev_shared,
                    is_ip_shared=is_ip_shared,
                    graph_risk_score=risk_score,
                )
        except Exception as exc:
            logger.warning(f"Neo4j get_user_graph_features query error for {user_id}: {exc}")
            return GraphRiskFeatures(
                user_id=user_id,
                device_fingerprint=current_device_fp,
                ip_address=current_ip,
            )

    def _inspect_transient_entities(
        self,
        user_id: str,
        device_fp: Optional[str],
        ip_addr: Optional[str],
    ) -> GraphRiskFeatures:
        """Inspects device and IP risk even for new users not yet committed to graph."""
        driver = get_neo4j_driver()
        if driver is None:
            return GraphRiskFeatures(user_id=user_id, device_fingerprint=device_fp, ip_address=ip_addr)

        dev_users = 1
        dev_frauds = 0
        ip_users = 1
        ip_frauds = 0

        try:
            with driver.session() as session:
                if device_fp:
                    res_d = session.run(
                        """
                        MATCH (d:Device {fingerprint: $fp})
                        OPTIONAL MATCH (d)<-[:USES_DEVICE]-(u:User)
                        OPTIONAL MATCH (d)<-[:ORIGINATED_FROM_DEVICE]-(t:Transaction WHERE t.is_fraud = true)
                        RETURN count(DISTINCT u) AS user_count, count(DISTINCT t) AS fraud_count
                        """,
                        {"fp": device_fp},
                    ).single()
                    if res_d:
                        dev_users = max(int(res_d["user_count"] or 1), 1)
                        dev_frauds = int(res_d["fraud_count"] or 0)

                if ip_addr and ip_addr not in ("0.0.0.0", ""):
                    res_ip = session.run(
                        """
                        MATCH (ip:IPAddress {address: $ip})
                        OPTIONAL MATCH (ip)<-[:USES_IP]-(u:User)
                        OPTIONAL MATCH (ip)<-[:ORIGINATED_FROM_IP]-(t:Transaction WHERE t.is_fraud = true)
                        RETURN count(DISTINCT u) AS user_count, count(DISTINCT t) AS fraud_count
                        """,
                        {"ip": ip_addr},
                    ).single()
                    if res_ip:
                        ip_users = max(int(res_ip["user_count"] or 1), 1)
                        ip_frauds = int(res_ip["fraud_count"] or 0)

            is_dev_shared = dev_users > 1
            is_ip_shared = ip_users > 1
            risk_score = min(1.0, (0.3 if is_dev_shared else 0.0) + (0.2 if is_ip_shared else 0.0) + (dev_frauds * 0.25) + (ip_frauds * 0.15))

            return GraphRiskFeatures(
                user_id=user_id,
                device_fingerprint=device_fp,
                ip_address=ip_addr,
                shared_device_user_count=dev_users,
                shared_ip_user_count=ip_users,
                shared_device_fraud_count=dev_frauds,
                shared_ip_fraud_count=ip_frauds,
                is_device_shared=is_dev_shared,
                is_ip_shared=is_ip_shared,
                graph_risk_score=risk_score,
            )
        except Exception as exc:
            logger.debug(f"Error checking transient entities in Neo4j: {exc}")
            return GraphRiskFeatures(user_id=user_id, device_fingerprint=device_fp, ip_address=ip_addr)

    def detect_fraud_rings(
        self,
        min_users_per_device: int = 2,
        min_users_per_ip: int = 3,
        limit: int = 25,
    ) -> List[FraudRingCluster]:
        """
        Discovers active fraud rings based on shared hardware fingerprints and dense IP reuse.
        """
        driver = get_neo4j_driver()
        if driver is None:
            return []

        cypher = """
        // 1. Devices shared by multiple users with elevated risk/fraud
        MATCH (d:Device)<-[:USES_DEVICE]-(u:User)
        WITH d, collect(DISTINCT u.id) AS user_ids, count(DISTINCT u) AS user_count
        WHERE user_count >= $min_users_per_device
        OPTIONAL MATCH (d)<-[:ORIGINATED_FROM_DEVICE]-(t:Transaction)
        RETURN
            'Device' AS entity_type,
            d.fingerprint AS entity_key,
            user_ids,
            user_count,
            collect(DISTINCT t.ref) AS txn_refs,
            sum(CASE WHEN t.is_fraud = true THEN t.amount ELSE 0.0 END) AS total_fraud_amount,
            count(CASE WHEN t.is_fraud = true THEN 1 ELSE NULL END) AS fraud_count
        ORDER BY fraud_count DESC, user_count DESC
        LIMIT $limit
        """

        rings: List[FraudRingCluster] = []
        try:
            with driver.session() as session:
                records = session.run(
                    cypher,
                    {"min_users_per_device": min_users_per_device, "limit": limit},
                )
                for i, rec in enumerate(records):
                    fraud_cnt = int(rec["fraud_count"] or 0)
                    user_cnt = int(rec["user_count"] or 0)
                    risk_lvl = "High" if (fraud_cnt > 0 or user_cnt >= 4) else "Medium"
                    rings.append(
                        FraudRingCluster(
                            ring_id=f"RING-DEV-{i+1:03d}",
                            primary_entity_type="Device",
                            entity_key=rec["entity_key"] or f"dev_{i}",
                            associated_users=rec["user_ids"] or [],
                            user_count=user_cnt,
                            associated_transactions=rec["txn_refs"] or [],
                            total_fraud_amount=float(rec["total_fraud_amount"] or 0.0),
                            confirmed_fraud_count=fraud_cnt,
                            risk_level=risk_lvl,
                            description=(
                                f"Hardware device shared across {user_cnt} distinct user accounts "
                                f"with {fraud_cnt} confirmed fraudulent transactions."
                            ),
                        )
                    )
        except Exception as exc:
            logger.warning(f"Neo4j detect_fraud_rings error: {exc}")

        return rings

    def get_entity_subgraph(
        self,
        entity_type: str,
        entity_id: str,
        depth: int = 2,
    ) -> SubgraphVisualization:
        """
        Extracts multi-hop subgraph for graph visualization in frontend Cytoscape / 3D Force-Graph.
        """
        driver = get_neo4j_driver()
        nodes_map: Dict[str, Dict[str, Any]] = {}
        links_list: List[Dict[str, Any]] = []

        if driver is None:
            # Return single root node if driver is offline
            return SubgraphVisualization(
                nodes=[{"id": entity_id, "label": entity_type, "properties": {"name": entity_id}}],
                edges=[],
                root_id=entity_id,
                entity_type=entity_type,
                depth=depth,
            )

        # Map entity type to Cypher label match
        cypher = f"""
        MATCH (root:{entity_type})
        WHERE root.id = $entity_id OR root.fingerprint = $entity_id OR root.address = $entity_id OR root.ref = $entity_id OR root.name = $entity_id
        MATCH path = (root)-[r*1..{min(depth, 3)}]-(neighbor)
        UNWIND nodes(path) AS n
        UNWIND relationships(path) AS rel
        RETURN
            elementId(n) AS node_elem_id,
            labels(n)[0] AS node_label,
            properties(n) AS node_props,
            elementId(startNode(rel)) AS source_elem_id,
            elementId(endNode(rel)) AS target_elem_id,
            type(rel) AS edge_type,
            properties(rel) AS edge_props
        LIMIT 150
        """

        try:
            with driver.session() as session:
                records = session.run(cypher, {"entity_id": str(entity_id)})
                for rec in records:
                    n_id = str(rec["node_elem_id"])
                    n_label = rec["node_label"]
                    n_props = rec["node_props"] or {}
                    # Normalize node display title
                    title = n_props.get("name") or n_props.get("id") or n_props.get("fingerprint") or n_props.get("address") or n_props.get("ref") or n_id

                    nodes_map[n_id] = {
                        "id": n_id,
                        "label": n_label,
                        "title": str(title),
                        "properties": n_props,
                    }

                    links_list.append({
                        "source": str(rec["source_elem_id"]),
                        "target": str(rec["target_elem_id"]),
                        "type": rec["edge_type"],
                        "properties": rec["edge_props"] or {},
                    })
        except Exception as exc:
            logger.warning(f"Neo4j get_entity_subgraph query error: {exc}")

        return SubgraphVisualization(
            nodes=list(nodes_map.values()),
            edges=links_list,
            root_id=entity_id,
            entity_type=entity_type,
            depth=depth,
        )

    def health_check(self) -> Dict[str, Any]:
        """Checks Neo4j driver connectivity, database name, and node counts."""
        driver = get_neo4j_driver()
        if driver is None:
            return {"status": "disabled_or_offline", "connected": False}

        try:
            start = time.time()
            with driver.session() as session:
                res = session.run(
                    """
                    MATCH (u:User) WITH count(u) as users
                    MATCH (d:Device) WITH users, count(d) as devices
                    MATCH (ip:IPAddress) WITH users, devices, count(ip) as ips
                    MATCH (t:Transaction) WITH users, devices, ips, count(t) as txns
                    RETURN users, devices, ips, txns
                    """
                ).single()
                latency_ms = round((time.time() - start) * 1000.0, 2)
                return {
                    "status": "healthy",
                    "connected": True,
                    "latency_ms": latency_ms,
                    "counts": {
                        "users": res["users"] if res else 0,
                        "devices": res["devices"] if res else 0,
                        "ips": res["ips"] if res else 0,
                        "transactions": res["txns"] if res else 0,
                    },
                }
        except Exception as exc:
            return {"status": "degraded", "connected": False, "error": str(exc)}
