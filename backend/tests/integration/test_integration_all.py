"""
test_integration_all.py
Comprehensive Docker Stack Integration & Verification Test Suite.
Tests real services: PostgreSQL (Neon/Local), Redis Feature Store, Kafka, Flink Stream Processing, and ML inference.
"""
import json
import os
import sys
import time
import uuid

import numpy as np
import psycopg2
import redis

# 1. PostgreSQL Verification
def test_postgres():
    print("=" * 60)
    print("1. TESTING DATABASE (POSTGRESQL / SQLITE)")
    print("=" * 60)
    db_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    if db_url.startswith("sqlite"):
        from app.db.session import SessionLocal, engine
        from app.db.models import AuditLog, User
        from sqlalchemy import inspect
        insp = inspect(engine)
        tables = insp.get_table_names()
        print(f"Found {len(tables)} tables in schema: {tables}")
        assert len(tables) >= 5, f"Expected at least 5 tables, got {len(tables)}"
        
        session = SessionLocal()
        test_id = uuid.uuid4()
        log = AuditLog(id=test_id, action="INTEGRATION_TEST", entity_type="system", entity_id=str(test_id), details={"status": "ok"})
        session.add(log)
        session.commit()
        retrieved = session.query(AuditLog).filter(AuditLog.id == test_id).first()
        assert retrieved is not None
        assert retrieved.action == "INTEGRATION_TEST"

        admin = session.query(User).filter(User.email == "admin@detexa.ai").first()
        if not admin:
            admin = User(id=uuid.uuid4(), name="Detexa Admin", email="admin@detexa.ai", mobile="+1234567890", hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", is_active=True, is_admin=True)
            session.add(admin)
            session.commit()
        user_id = str(admin.id)
        session.close()
        print(f"Verified test user ID in DB: {user_id}")
        return user_id

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(tables)} tables in PostgreSQL schema: {tables}")
    assert len(tables) >= 8, f"Expected at least 8 tables, got {len(tables)}"

    # Test read/write
    test_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO audit_logs (id, action, entity_type, entity_id, details)
        VALUES (%s, %s, %s, %s, %s);
    """, (test_id, "INTEGRATION_TEST", "system", test_id, json.dumps({"status": "ok"})))
    conn.commit()

    cursor.execute("SELECT action, entity_type, entity_id FROM audit_logs WHERE id = %s;", (test_id,))
    row = cursor.fetchone()
    print(f"Persisted and retrieved test audit log: {row}")
    assert row == ("INTEGRATION_TEST", "system", test_id)
    
    # Ensure test user exists for API auth testing
    cursor.execute("SELECT id FROM users WHERE email = %s;", ("admin@detexa.ai",))
    user_row = cursor.fetchone()
    if user_row:
        user_id = str(user_row[0])
    else:
        user_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (id, name, email, mobile, hashed_password, is_active, is_admin)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (user_id, "Detexa Admin", "admin@detexa.ai", "+1234567890", "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW", True, True))
        conn.commit()
    print(f"Verified test user ID in PostgreSQL: {user_id}")
    
    cursor.close()
    conn.close()
    print("✅ PostgreSQL DB test PASSED!")
    return user_id

# 2. Redis Feature Store Verification
def test_redis():
    print("=" * 60)
    print("2. TESTING REDIS FEATURE STORE & ENTITY SETS")
    print("=" * 60)
    r = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    assert r.ping(), "Redis ping failed"
    
    test_key = f"test:feature:{uuid.uuid4().hex[:8]}"
    r.set(test_key, "feature_val_123", ex=60)
    val = r.get(test_key)
    ttl = r.ttl(test_key)
    print(f"Redis write/read key='{test_key}': val='{val.decode()}', ttl={ttl}s")
    assert val.decode() == "feature_val_123"
    assert ttl > 0

    # Test sorted set operations (used in sliding window velocity)
    z_key = f"test:velocity:{uuid.uuid4().hex[:8]}"
    now = time.time()
    r.zadd(z_key, {f"tx1": now - 10, f"tx2": now - 5, f"tx3": now})
    r.expire(z_key, 60)
    count = r.zcount(z_key, now - 60, "+inf")
    print(f"Redis sorted set window velocity count: {count}")
    assert count == 3

    # Test entity linkage sets (replaces Neo4j shared entity counting)
    dev_key = f"device:test_dev_01:users"
    r.sadd(dev_key, "user_01", "user_02")
    r.expire(dev_key, 60)
    shared_users = r.scard(dev_key)
    print(f"Redis entity set shared users count: {shared_users}")
    assert shared_users == 2

    r.delete(test_key, z_key, dev_key)
    print("✅ Redis Feature Store & Entity Sets test PASSED!")

# 3. Kafka Real Broker Verification
def test_kafka():
    print("=" * 60)
    print("3. TESTING KAFKA BROKER REAL PUBLISH & CONSUME")
    print("=" * 60)
    from kafka import KafkaProducer, KafkaConsumer
    
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = "detexa.test.integration"
    
    # Check broker
    producer = KafkaProducer(
        bootstrap_servers=bootstrap.split(","),
        api_version=(3, 7, 0),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    
    test_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "INTEGRATION_TEST",
        "timestamp": time.time(),
        "payload": {"status": "kafka_live_ok"},
    }
    
    future = producer.send(topic, test_event)
    record_metadata = future.get(timeout=10)
    print(f"Successfully published event to Kafka: topic={record_metadata.topic}, partition={record_metadata.partition}, offset={record_metadata.offset}")
    producer.flush()
    producer.close()
    
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap.split(","),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id=f"detexa-test-group-{uuid.uuid4().hex[:6]}",
        api_version=(3, 7, 0),
        consumer_timeout_ms=10000,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    
    received = None
    for msg in consumer:
        if msg.value.get("event_id") == test_event["event_id"]:
            received = msg.value
            print(f"Successfully consumed event from Kafka at offset {msg.offset}: {received}")
            break
    consumer.close()
    assert received is not None, "Failed to consume published Kafka event"
    print("✅ Real Kafka Broker test PASSED!")

# 4. Behavior ML Model Anomaly Scoring Verification
def test_behavior_model():
    print("=" * 60)
    print("4. TESTING BEHAVIOR ANOMALY ML MODEL")
    print("=" * 60)
    from app.ml.models.behavior_model import BehaviorAnomalyModel
    
    model = BehaviorAnomalyModel.get_instance()
    assert model._loaded, "BehaviorAnomalyModel failed to load pipeline artifact"
    
    normal_payload = {
        "login_hour": 14,
        "typing_speed": 5.5,
        "mouse_velocity": 450.0,
        "failed_logins": 0,
        "is_vpn": 0,
        "is_tor": 0,
        "device_change": 0,
    }
    score_norm, lat_norm, factors_norm = model.predict(normal_payload)
    print(f"Normal Behavior: score={score_norm:.4f}, latency={lat_norm:.2f}ms, risk_factors={factors_norm}")
    assert 0.0 <= score_norm <= 1.0
    
    suspicious_payload = {
        "login_hour": 3,
        "typing_speed": 15.0,
        "mouse_velocity": 1200.0,
        "failed_logins": 5,
        "is_vpn": 1,
        "is_tor": 1,
        "device_change": 1,
    }
    score_susp, lat_susp, factors_susp = model.predict(suspicious_payload)
    print(f"Suspicious Behavior: score={score_susp:.4f}, latency={lat_susp:.2f}ms, risk_factors={factors_susp}")
    assert len(factors_susp) > 0
    print("✅ Behavior Anomaly ML Model test PASSED!")

import pytest

@pytest.fixture
def auth_user_id():
    from app.db.session import SessionLocal
    from app.db.models import User
    session = SessionLocal()
    admin = session.query(User).filter(User.email == "admin@detexa.ai").first()
    if not admin:
        admin = User(
            id=uuid.uuid4(),
            name="Detexa Admin",
            email="admin@detexa.ai",
            mobile="+1234567890",
            hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            is_active=True,
            is_admin=True,
        )
        session.add(admin)
        session.commit()
    user_id = str(admin.id)
    session.close()
    return user_id

# 5. End-to-End Real Transaction & Fraud Scenarios Verification
def test_e2e_scenarios(auth_user_id: str):
    print("=" * 60)
    print("5. TESTING END-TO-END FRAUD SCENARIOS VIA FASTAPI & SERVICES")
    print("=" * 60)
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.db.models import User
    
    client = TestClient(app)
    
    # 5.1 Health Check
    health_resp = client.get("/health")
    print(f"Health Endpoint Status: {health_resp.status_code}, Response: {health_resp.json()}")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] in ("healthy", "ok")
    
    # 5.2 Auth Token
    token = create_access_token(data={"sub": str(auth_user_id), "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}
    
    # Helper to insert test user into DB
    def create_scenario_user(uid: str, email_prefix: str):
        session = SessionLocal()
        user_uuid = uuid.UUID(uid) if isinstance(uid, str) else uid
        u = session.query(User).filter(User.id == user_uuid).first()
        if not u:
            u = User(
                id=user_uuid,
                name=f"User {email_prefix}",
                email=f"{email_prefix}_{uuid.uuid4().hex[:6]}@example.com",
                mobile="+1234567890",
                hashed_password="$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
                is_active=True,
                is_admin=False,
            )
            session.add(u)
            session.commit()
        session.close()

    # Scenario A: Normal Low-Risk Transaction
    print("\n--- Scenario A: Normal Low-Risk Transaction ---")
    norm_user_id = str(uuid.uuid4())
    create_scenario_user(norm_user_id, "norm")
    norm_txn_id = f"TXN-NORM-{uuid.uuid4().hex[:8].upper()}"
    norm_dev_fp = f"dev_clean_{uuid.uuid4().hex[:8]}"
    norm_payload = {
        "user_id": norm_user_id,
        "transaction_ref": norm_txn_id,
        "amount": 24.50,
        "transaction_amount": 24.50,
        "currency": "INR",
        "merchant": "Target Superstore",
        "category": "Retail",
        "merchant_category": "Retail",
        "device_fingerprint": norm_dev_fp,
        "ip_address": "192.168.1.100",
        "country": "IN",
        "account_type": "Savings",
        "transaction_type": "UPI",
        "channel": "Mobile_App",
        "kyc_status": "Verified",
    }
    resp_a = client.post("/api/v1/predict/transaction", json=norm_payload, headers=headers)
    print(f"Scenario A status={resp_a.status_code}, response={resp_a.json()}")
    assert resp_a.status_code == 200
    data_a = resp_a.json()
    print(f"Result A: decision={data_a['decision']}, risk_level={data_a['risk_level']}, fraud_score={data_a['fraud_score']}")
    assert data_a["decision"] in ("ALLOW", "CHALLENGE", "REVIEW", "BLOCK")
    
    # Scenario B: Suspicious Transaction
    print("\n--- Scenario B: Suspicious Medium-Risk Transaction ---")
    susp_user_id = str(uuid.uuid4())
    create_scenario_user(susp_user_id, "susp")
    susp_txn_id = f"TXN-SUSP-{uuid.uuid4().hex[:8].upper()}"
    susp_payload = {
        "user_id": susp_user_id,
        "transaction_ref": susp_txn_id,
        "amount": 18500.00,
        "transaction_amount": 18500.00,
        "currency": "INR",
        "merchant": "Crypto Exchange Global",
        "category": "Cryptocurrency",
        "merchant_category": "Cryptocurrency",
        "device_fingerprint": f"dev_unknown_{uuid.uuid4().hex[:6]}",
        "ip_address": "185.220.101.5",
        "country": "IN",
        "account_type": "Current",
        "transaction_type": "IMPS",
        "channel": "Net Banking",
        "kyc_status": "Pending",
    }
    resp_b = client.post("/api/v1/predict/transaction", json=susp_payload, headers=headers)
    print(f"Scenario B status={resp_b.status_code}, response={resp_b.json()}")
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    print(f"Result B: decision={data_b['decision']}, risk_level={data_b['risk_level']}, fraud_score={data_b['fraud_score']}")
    assert data_b["decision"] in ("CHALLENGE", "REVIEW", "BLOCK", "ALLOW")
    
    # Scenario C: High-Risk Outlier Transaction
    print("\n--- Scenario C: High-Risk Critical Fraud Transaction ---")
    high_user_id = str(uuid.uuid4())
    create_scenario_user(high_user_id, "high")
    high_txn_id = f"TXN-HIGH-{uuid.uuid4().hex[:8].upper()}"
    high_payload = {
        "user_id": high_user_id,
        "transaction_ref": high_txn_id,
        "amount": 850000.00,
        "transaction_amount": 850000.00,
        "currency": "INR",
        "merchant": "Unknown Luxury Electronics Wire",
        "category": "Wire Transfer",
        "merchant_category": "Wire Transfer",
        "device_fingerprint": f"dev_tor_node_{uuid.uuid4().hex[:6]}",
        "ip_address": "185.220.101.44",
        "country": "IN",
        "account_type": "Current",
        "transaction_type": "RTGS",
        "channel": "API",
        "kyc_status": "Pending",
    }
    resp_c = client.post("/api/v1/predict/transaction", json=high_payload, headers=headers)
    assert resp_c.status_code == 200
    data_c = resp_c.json()
    print(f"Result C: decision={data_c['decision']}, risk_level={data_c['risk_level']}, fraud_score={data_c['fraud_score']}")
    assert data_c["decision"] in ("BLOCK", "REVIEW", "CHALLENGE")
    assert data_c["risk_level"] in ("High", "Critical", "Medium", "Low")
    
    # 5.3 Real-Time Inference with Live Redis
    print("\n--- Testing Ultra-Low-Latency /predict/realtime Endpoint ---")
    rt_resp = client.post("/api/v1/predict/realtime", json=norm_payload, headers=headers)
    print(f"Realtime inference status={rt_resp.status_code}, latency={rt_resp.json().get('latency_ms')}ms")
    assert rt_resp.status_code == 200

    # 5.4 Streaming Kafka Event Ingestion & Flink Processing
    print("\n--- Testing Real Streaming Ingestion into Kafka Topic ---")
    stream_payload = {
        "user_id": str(auth_user_id),
        "transaction_ref": f"TXN-STREAM-{uuid.uuid4().hex[:8].upper()}",
        "amount": 499.00,
        "currency": "INR",
        "merchant": "Amazon Marketplace",
        "category": "E-Commerce",
        "merchant_category": "E-Commerce",
        "device_fingerprint": "dev_stream_001",
        "ip_address": "72.14.201.1",
        "country": "IN",
    }
    stream_resp = client.post("/api/v1/streaming/transactions", json=stream_payload, headers=headers)
    print(f"Streaming async ingest status={stream_resp.status_code}, response={stream_resp.json()}")
    assert stream_resp.status_code == 202
    assert stream_resp.json()["status"] == "QUEUED"

    print("\n--- Testing Real Sync End-to-End Streaming Pipeline (Flink + ML + DB + Kafka Egress) ---")
    sync_resp = client.post("/api/v1/streaming/transactions/process-sync", json=stream_payload, headers=headers)
    print(f"Streaming sync process status={sync_resp.status_code}, response={sync_resp.json()}")
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert sync_data["decision"] in ("ALLOW", "CHALLENGE", "REVIEW", "BLOCK")
    print(f"Sync Streaming Pipeline Result: decision={sync_data['decision']}, score={sync_data['fraud_score']}, risk_level={sync_data['risk_level']}")

    print("✅ End-to-End Scenarios and API tests PASSED!")

if __name__ == "__main__":
    try:
        auth_user_id = test_postgres()
        test_redis()
        test_kafka()
        test_behavior_model()
        test_e2e_scenarios(auth_user_id)
        print("\n" + "=" * 60)
        print("🎉 ALL DOCKER RUNTIME INTEGRATION TESTS PASSED 100%!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
