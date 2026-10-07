"""
backend/tests/integration/test_neo4j_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests connecting directly to the real Neo4j graph database.
"""

import pytest
import uuid
import time
from neo4j import GraphDatabase


@pytest.mark.integration
class TestNeo4jIntegration:
    @classmethod
    def setup_class(cls):
        # Try localhost or neo4j hostname
        try:
            cls.driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "detexa_neo4j_password"))
            with cls.driver.session() as s:
                s.run("RETURN 1 AS ping")
        except Exception:
            cls.driver = GraphDatabase.driver("bolt://neo4j:7687", auth=("neo4j", "detexa_neo4j_password"))
            with cls.driver.session() as s:
                s.run("RETURN 1 AS ping")

    @classmethod
    def teardown_class(cls):
        cls.driver.close()

    def test_neo4j_bolt_connection(self):
        with self.driver.session() as session:
            result = session.run("RETURN 'Neo4j Live' AS msg")
            record = result.single()
            assert record["msg"] == "Neo4j Live"

    def test_fraud_ring_shared_device_cypher_detection(self):
        user_a = f"u_a_{uuid.uuid4().hex[:6]}"
        user_b = f"u_b_{uuid.uuid4().hex[:6]}"
        device_id = f"dev_{uuid.uuid4().hex[:6]}"

        with self.driver.session() as session:
            # 1. Create shared device topology
            session.run("""
                MERGE (u1:User {id: $u1})
                MERGE (u2:User {id: $u2})
                MERGE (d:Device {id: $dev})
                MERGE (u1)-[:USED_DEVICE]->(d)
                MERGE (u2)-[:USED_DEVICE]->(d)
            """, u1=user_a, u2=user_b, dev=device_id)

            # 2. Query shared device count
            query = """
                MATCH (u:User {id: $u1})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(other:User)
                RETURN count(DISTINCT other) AS shared_user_count, d.id AS device_id
            """
            res = session.run(query, u1=user_a).single()
            assert res is not None
            assert res["shared_user_count"] >= 1
            assert res["device_id"] == device_id

            # 3. Clean up
            session.run("""
                MATCH (u:User) WHERE u.id IN [$u1, $u2] DETACH DELETE u
            """, u1=user_a, u2=user_b)
            session.run("""
                MATCH (d:Device {id: $dev}) DETACH DELETE d
            """, dev=device_id)
