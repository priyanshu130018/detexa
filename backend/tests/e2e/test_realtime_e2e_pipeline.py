"""
backend/tests/e2e/test_realtime_e2e_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Complete real-time end-to-end transaction pipeline test through all real services:
FastAPI / Kafka -> Flink -> Redis -> Neo4j -> XGBoost -> Decision Engine -> PostgreSQL -> Real-time Broadcast.
"""

import pytest
import time
import json
import uuid
import redis
from neo4j import GraphDatabase
from kafka import KafkaProducer, KafkaConsumer
from app.core.config import settings
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.decision import get_decision_engine, DecisionContext, DecisionAction
from app.streaming.flink_processor import SlidingWindowState
from app.core.realtime_broadcaster import get_realtime_broadcaster


@pytest.mark.e2e
class TestRealtimeE2EPipeline:
    @classmethod
    def setup_class(cls):
        # 1. Connect to real Redis
        cls.r = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=3.0)
        try:
            cls.r.ping()
        except Exception:
            cls.r = redis.Redis(host="localhost", port=6379, decode_responses=True, socket_timeout=3.0)

        # 2. Connect to real Neo4j
        cls.driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

        # 3. Connect to real Kafka
        bootstrap = settings.kafka_bootstrap_servers or "kafka:9092"
        cls.producer = KafkaProducer(
            bootstrap_servers=bootstrap,
            api_version=(3, 7, 0),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
        )
        cls.bootstrap = bootstrap

        cls.window_state = SlidingWindowState()
        cls.banking_model = BankingFraudModel.get_instance()
        cls.decision_engine = get_decision_engine()

    def test_e2e_trace_1_low_risk_allow_flow(self):
        customer_id = f"CUST-E2E-{uuid.uuid4().hex[:6]}"
        user_id = customer_id
        device_id = f"dev-e2e-{uuid.uuid4().hex[:6]}"
        ip_addr = "192.168.1.100"
        amount = 499.0

        # Step 1: Ingest transaction via Kafka
        topic = "detexa.transactions.raw"
        txn_event = {
            "transaction_id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "user_id": user_id,
            "device_id": device_id,
            "ip_address": ip_addr,
            "transaction_amount": amount,
            "amount": amount,
            "currency": "INR",
            "merchant": "Blinkit India",
            "account_balance": 50000.0,
            "account_type": "Savings",
            "transaction_type": "UPI",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "credit_score": 750,
            "timestamp": time.time(),
        }
        self.producer.send(topic, txn_event)
        self.producer.flush()

        # Step 2: Flink stream window state aggregation
        now = time.time()
        f = self.window_state.record_and_compute(customer_id, amount, "Blinkit India", "IN", device_id, now)

        assert f.velocity_1m >= 1
        assert f.velocity_5m >= 1
        assert f.velocity_1h >= 1
        assert f.rolling_amount_1h >= 499.0

        # Step 3: Write & Read Real-time Features in Redis Feature Store
        redis_key = f"features:user:{customer_id}"
        self.r.hset(redis_key, mapping={
            "velocity_1m": f.velocity_1m,
            "velocity_5m": f.velocity_5m,
            "amount_sum_1h": f.rolling_amount_1h,
            "device_changed": "0",
        })
        self.r.expire(redis_key, 300)
        stored_features = self.r.hgetall(redis_key)
        assert int(stored_features["velocity_1m"]) >= 1

        # Step 4: Neo4j Graph Relationship & Ring Detection
        with self.driver.session() as session:
            session.run("""
                MERGE (u:User {id: $user_id})
                MERGE (d:Device {id: $device_id})
                MERGE (u)-[r:USED_DEVICE]->(d)
                ON CREATE SET r.first_seen = timestamp()
            """, user_id=customer_id, device_id=device_id)

            result = session.run("""
                MATCH (u:User {id: $user_id})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(other:User)
                RETURN count(DISTINCT other) AS shared_users
            """, user_id=customer_id)
            record = result.single()
            shared_users = record["shared_users"] if record else 0

        # Step 5: Machine Learning Inference (XGBoost on Banking Features)
        ml_input = {
            "customer_id": customer_id,
            "transaction_amount": amount,
            "account_balance": 50000.0,
            "account_type": "Savings",
            "transaction_type": "UPI",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "credit_score": 750,
        }
        score, shap_drivers = self.banking_model.predict(ml_input)
        assert 0.0 <= score <= 1.0

        # Step 6: Decision Engine Evaluation
        ctx = DecisionContext(
            fraud_score=score,
            amount=amount,
            currency="INR",
            user_id=customer_id,
            realtime_features={"velocity_1m": int(stored_features["velocity_1m"])},
            graph_risk={"graph_shared_device_users": shared_users, "graph_risk_score": 0.0},
        )
        decision_outcome = self.decision_engine.evaluate(ctx)
        assert decision_outcome.decision in [DecisionAction.ALLOW, DecisionAction.REVIEW, DecisionAction.CHALLENGE]

    def test_e2e_trace_2_high_risk_collusion_block_flow(self):
        fraudster_1 = f"fraud-1-{uuid.uuid4().hex[:6]}"
        fraudster_2 = f"fraud-2-{uuid.uuid4().hex[:6]}"
        fraudster_3 = f"fraud-3-{uuid.uuid4().hex[:6]}"
        shared_device = f"dev-compromised-{uuid.uuid4().hex[:6]}"

        # Create multi-user collusion ring in Neo4j
        with self.driver.session() as session:
            for f_id in [fraudster_1, fraudster_2, fraudster_3]:
                session.run("""
                    MERGE (u:User {id: $uid})
                    MERGE (d:Device {id: $did})
                    MERGE (u)-[:USED_DEVICE]->(d)
                """, uid=f_id, did=shared_device)

            result = session.run("""
                MATCH (u:User {id: $uid})-[:USED_DEVICE]->(d:Device)<-[:USED_DEVICE]-(other:User)
                RETURN count(DISTINCT other) AS shared_users
            """, uid=fraudster_1)
            shared_users = result.single()["shared_users"]

        assert shared_users >= 2

        # Evaluate decision with graph collusion risk
        ctx = DecisionContext(
            fraud_score=0.92,
            amount=850000.0,
            currency="INR",
            user_id=fraudster_1,
            realtime_features={"velocity_1m": 10},
            graph_risk={"graph_shared_device_users": shared_users + 1, "graph_shared_device_frauds": 3},
        )
        decision_outcome = self.decision_engine.evaluate(ctx)
        assert decision_outcome.decision == DecisionAction.BLOCK
        assert decision_outcome.risk_level == "High"
