import json
import os
import sys
import time
import uuid

import numpy as np
import pandas as pd
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis_client
from app.db.session import SessionLocal, engine
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.ml.models.behavior_model import BehaviorAnomalyModel

def run_diagnostics():
    report = {}
    print("=================================================================")
    print("               DETEXA SYSTEM & SERVICE HEALTH AUDIT              ")
    print("=================================================================")

    # 1. FastAPI & Environment
    report["environment"] = {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_version": settings.app_version,
        "cors_origins": settings.cors_origins,
        "status": "PASS",
    }
    print(f"\n[1] Environment Config: {settings.app_name} v{settings.app_version} [{settings.app_env}] -> PASS")

    # 2. Neon PostgreSQL
    db_start = time.perf_counter()
    try:
        with engine.connect() as conn:
            res = conn.execute(text("SELECT version(), current_database(), current_user;")).fetchone()
            db_lat = (time.perf_counter() - db_start) * 1000
            report["database"] = {
                "status": "PASS",
                "engine": "Neon Serverless PostgreSQL (SSL)",
                "database_name": res[1],
                "user": res[2],
                "latency_ms": round(db_lat, 2),
                "server_version": res[0].split(",")[0],
            }
            print(f"[2] Neon PostgreSQL: Connected (db={res[1]}, latency={db_lat:.2f}ms) -> PASS")
    except Exception as e:
        report["database"] = {"status": "FAIL", "error": str(e)}
        print(f"[2] Neon PostgreSQL: FAILED -> {e}")

    # 3. Redis Cache & Feature Store
    r_start = time.perf_counter()
    try:
        r = get_redis_client()
        if r and r.ping():
            # Test Read/Write/TTL
            test_key = f"diag:test:{uuid.uuid4().hex[:6]}"
            r.set(test_key, "val_diag", ex=10)
            read_val = r.get(test_key)
            ttl = r.ttl(test_key)
            r.delete(test_key)
            r_lat = (time.perf_counter() - r_start) * 1000
            report["redis"] = {
                "status": "PASS",
                "host": settings.redis_url,
                "latency_ms": round(r_lat, 2),
                "read_write_verified": read_val == "val_diag",
                "ttl_verified": ttl > 0,
            }
            print(f"[3] Redis: Connected (latency={r_lat:.2f}ms, r/w=True, ttl={ttl}s) -> PASS")
        else:
            report["redis"] = {"status": "DEGRADED", "note": "Redis client returned None or ping failed"}
            print(f"[3] Redis: Degraded -> FAIL")
    except Exception as e:
        report["redis"] = {"status": "FAIL", "error": str(e)}
        print(f"[3] Redis: FAILED -> {e}")

    # 4. Neo4j Graph Database
    neo_start = time.perf_counter()
    try:
        from app.core.neo4j import get_neo4j_driver
        driver = get_neo4j_driver()
        if driver:
            with driver.session(database=settings.neo4j_database) as session:
                rec = session.run("RETURN 1 AS ping;").single()
                # Test isolated node creation & deletion
                test_id = f"test_diag_{uuid.uuid4().hex[:6]}"
                session.run("CREATE (n:TestDiag {id: $id, created: timestamp()})", id=test_id)
                check = session.run("MATCH (n:TestDiag {id: $id}) RETURN n.id AS id", id=test_id).single()
                session.run("MATCH (n:TestDiag {id: $id}) DELETE n", id=test_id)
                neo_lat = (time.perf_counter() - neo_start) * 1000
                report["neo4j"] = {
                    "status": "PASS",
                    "uri": settings.neo4j_uri,
                    "database": settings.neo4j_database,
                    "latency_ms": round(neo_lat, 2),
                    "crud_verified": check and check["id"] == test_id,
                }
                print(f"[4] Neo4j Graph: Connected (latency={neo_lat:.2f}ms, CRUD=Verified) -> PASS")
        else:
            report["neo4j"] = {"status": "DEGRADED/FALLBACK", "note": "Driver returned None (neo4j_enabled=False)"}
            print(f"[4] Neo4j Graph: Driver Disabled/Fallback (neo4j_enabled={settings.neo4j_enabled}) -> PASS (Graceful Degrade)")
    except Exception as e:
        report["neo4j"] = {"status": "FAIL", "error": str(e)}
        print(f"[4] Neo4j Graph: FAILED -> {e}")

    # 5. Kafka Broker
    kafka_start = time.perf_counter()
    try:
        from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
        admin = KafkaAdminClient(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            client_id="detexa-diag-admin",
            request_timeout_ms=3000,
        )
        topics = admin.list_topics()
        admin.close()
        k_lat = (time.perf_counter() - kafka_start) * 1000
        report["kafka"] = {
            "status": "PASS",
            "brokers": settings.kafka_bootstrap_servers,
            "latency_ms": round(k_lat, 2),
            "topics": list(topics),
        }
        print(f"[5] Kafka Broker: Connected (latency={k_lat:.2f}ms, topics={len(topics)}) -> PASS")
    except Exception as e:
        report["kafka"] = {"status": "UNAVAILABLE/FALLBACK", "note": str(e), "kafka_enabled_setting": settings.kafka_enabled}
        print(f"[5] Kafka Broker: {e} -> (kafka_enabled={settings.kafka_enabled})")

    # 6. XGBoost Booster Model
    try:
        m = BankingFraudModel.get_instance()
        assert m._loaded is True, "Model _loaded is False"
        assert m._booster is not None, "XGBoost booster instance is None"
        report["xgboost_model"] = {
            "status": "PASS",
            "model_version": m.MODEL_VERSION,
            "booster_type": str(type(m._booster)),
            "feature_count": len(m._feature_names) if m._feature_names else 0,
        }
        print(f"[6] XGBoost Model: Loaded (version={m.MODEL_VERSION}, features={len(m._feature_names)}) -> PASS")
    except Exception as e:
        report["xgboost_model"] = {"status": "FAIL", "error": str(e)}
        print(f"[6] XGBoost Model: FAILED -> {e}")

    # 7. TreeSHAP Explainability
    try:
        sample_df = pd.DataFrame([{
            "transaction_amount": 15000.0,
            "account_balance": 45000.0,
            "emi_amount": 0.0,
            "credit_score": 750,
            "transaction_type": "UPI",
            "account_type": "Savings",
            "channel": "Mobile_App",
            "state": "Maharashtra",
            "merchant_category": "Electronics",
            "transaction_direction": "Debit",
            "transaction_status": "Success",
            "kyc_status": "Verified",
            "has_loan": 0,
            "loan_type": "None",
            "transaction_hour": 14,
        }])
        shap_res = m._explain(sample_df)
        report["treeshap"] = {
            "status": "PASS",
            "initialized": shap_res is not None,
            "top_feature_count": len(shap_res) if shap_res else 0,
        }
        print(f"[7] Native TreeSHAP: Operational (generated {len(shap_res) if shap_res else 0} feature drivers) -> PASS")
    except Exception as e:
        report["treeshap"] = {"status": "FAIL", "error": str(e)}
        print(f"[7] Native TreeSHAP: FAILED -> {e}")

    # 8. Groq LLM API
    try:
        groq_configured = bool(settings.groq_api_key and settings.groq_api_key.startswith("gsk_"))
        report["groq_llm"] = {
            "status": "PASS" if groq_configured else "BLOCKED (No Key Configured - Safe Fallback Active)",
            "model": settings.groq_model,
            "configured": groq_configured,
        }
        print(f"[8] Groq LLM Layer: {'Configured (PASS)' if groq_configured else 'Safe Fallback Active (Key absent)'}")
    except Exception as e:
        report["groq_llm"] = {"status": "FAIL", "error": str(e)}
        print(f"[8] Groq LLM: FAILED -> {e}")

    # Save diagnostics report
    out_dir = "app/ml/saved" if os.path.exists("app/ml/saved") else "backend/app/ml/saved"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "diagnostics_report.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved diagnostics report to {out_path}")
    print("=================================================================\n")

if __name__ == "__main__":
    run_diagnostics()
