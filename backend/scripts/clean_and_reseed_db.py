"""
scripts/clean_and_reseed_db.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive database cleaner & Indian demo data rebuilding script for Detexa.
1. Inspects and purges existing non-Indian / test records across application tables.
2. Preserves all table schemas, constraints, indexes, and Alembic history.
3. Inserts realistic Indian demo records (Users, Merchants, IP addresses, Devices).
4. Generates transactions with INR values and passes each through the real
   ML inference engine & Decision rules engine to compute genuine predictions,
   SHAP values, decisions, and fraud alerts.
5. Flushes Redis caches to ensure immediate dashboard alignment.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
import uuid

sys.stdout.reconfigure(encoding='utf-8')

# Insert backend root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.security import hash_password
from app.db.models import (
    AlertStatus,
    AuditLog,
    BehaviorLog,
    DecisionType,
    Device,
    FraudAlert,
    FraudPrediction,
    IPAddress,
    Merchant,
    ModelMetadata,
    RiskLevel,
    Transaction,
    User,
)
from app.db.session import engine, SessionLocal
from app.decision import DecisionAction, DecisionContext, get_decision_engine
from app.ml.inference.service import FraudInferenceService


def clean_database(db: Session):
    print("\n========================================================")
    print("STEP 1: CLEANING DATABASE (PRESERVING SCHEMA & MIGRATIONS)")
    print("========================================================")
    
    # Verify current row counts
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Discovered tables in Neon PostgreSQL: {tables}")

    # Delete records in strict reverse foreign-key dependency order
    deletion_order = [
        "fraud_alerts",
        "fraud_predictions",
        "behavior_logs",
        "audit_logs",
        "transactions",
        "devices",
        "ip_addresses",
        "merchants",
        "users",
        "model_metadata",
    ]

    for tbl in deletion_order:
        if tbl in tables:
            del_stmt = text(f'DELETE FROM "{tbl}"')
            result = db.execute(del_stmt)
            print(f"  ✓ Purged table '{tbl}': {result.rowcount} rows deleted.")

    db.commit()
    print("Database purge completed successfully.")


def reseed_indian_demo_data(db: Session):
    print("\n========================================================")
    print("STEP 2: RESEEDING CANONICAL INDIAN DEMO DATA")
    print("========================================================")
    
    now = datetime.now(timezone.utc)
    rng = random.Random(42)

    # ── 1. Model Metadata ────────────────────────────────────────────────────
    print("Registering Active Indian ML Models...")
    banking_model_meta = ModelMetadata(
        id=uuid.uuid4(),
        model_name="IndianBankingFraudXGBoost",
        version="2.0.0",
        algorithm="XGBoost Classifier + Native TreeSHAP",
        threshold=0.50,
        is_active=True,
        metrics={
            "pr_auc": 0.017,
            "roc_auc": 0.5283,
            "f1": 0.0824,
            "precision": 0.0789,
            "recall": 0.0862,
            "optimal_threshold": 0.65,
        },
        trained_at=now - timedelta(days=7),
    )
    behavior_model_meta = ModelMetadata(
        id=uuid.uuid4(),
        model_name="BehaviorAnomalyModel",
        version="1.0.0",
        algorithm="Isolation Forest + Heuristic Anomaly Scoring",
        threshold=0.50,
        is_active=True,
        metrics={"contamination": 0.05, "n_estimators": 100},
        trained_at=now - timedelta(days=90),
    )
    db.add(banking_model_meta)
    db.add(behavior_model_meta)
    db.flush()

    # ── 2. Indian Users ──────────────────────────────────────────────────────
    print("Seeding Indian Users & Analysts...")
    users_data = [
        ("Priyanshu", "priyanshu@gmail.com", "+91-9876543211", True, "Admin@1234"),
        ("Admin User", "admin@detexa.ai", "+91-9876543210", True, "Admin@1234"),
        ("Priya Sharma", "priya.sharma@detexa.ai", "+91-9820112233", True, "Analyst@1234"),
        ("Aarav Patel", "aarav.patel@example.in", "+91-9811223344", False, "User@1234"),
        ("Rohit Verma", "rohit.verma@example.in", "+91-9822334455", False, "User@1234"),
        ("Ananya Iyer", "ananya.iyer@example.in", "+91-9833445566", False, "User@1234"),
        ("Vikram Singh", "vikram.singh@example.in", "+91-9844556677", False, "User@1234"),
        ("Neha Gupta", "neha.gupta@example.in", "+91-9855667788", False, "User@1234"),
        ("Rahul Deshmukh", "rahul.deshmukh@example.in", "+91-9866778899", False, "User@1234"),
    ]

    users: list[User] = []
    admin_user = None
    analyst_user = None

    for name, email, mob, is_adm, pwd in users_data:
        u = User(
            id=uuid.uuid4(),
            name=name,
            email=email,
            mobile=mob,
            hashed_password=hash_password(pwd),
            is_admin=is_adm,
            is_active=True,
            created_at=now - timedelta(days=rng.randint(30, 180)),
            last_login=now - timedelta(hours=rng.randint(1, 48)),
        )
        db.add(u)
        users.append(u)
        if email == "admin@detexa.ai":
            admin_user = u
        elif email == "priya.sharma@detexa.ai":
            analyst_user = u

    db.flush()
    print(f"  ✓ Inserted {len(users)} users (including Admin & Fraud Analyst).")

    # ── 3. Indian Merchants ──────────────────────────────────────────────────
    print("Seeding Authentic Indian Merchants...")
    merchant_defs = [
        ("Swiggy India", "Food & Dining", 0.02),
        ("Zomato Payments", "Food & Dining", 0.02),
        ("Flipkart Internet", "E-Commerce", 0.04),
        ("Amazon India", "E-Commerce", 0.03),
        ("Reliance Digital", "Retail", 0.05),
        ("D-Mart Supermarket", "Retail", 0.01),
        ("Tata Power Mumbai", "Utilities", 0.01),
        ("IRCTC Rail Connect", "Travel", 0.02),
        ("Apollo Pharmacy", "Healthcare", 0.01),
        ("Zerodha Broking", "Investment", 0.06),
        ("Tanishq Jewellery", "Retail", 0.18),
        ("MakeMyTrip India", "Travel", 0.08),
        ("Unknown P2P Crypto Gateway", "Retail", 0.65),
    ]

    merchants: list[Merchant] = []
    for name, cat, risk_s in merchant_defs:
        m = Merchant(
            id=uuid.uuid4(),
            name=name,
            category=cat,
            risk_score=risk_s,
            created_at=now - timedelta(days=180),
        )
        db.add(m)
        merchants.append(m)
    db.flush()
    print(f"  ✓ Inserted {len(merchants)} Indian merchants across key categories.")

    # ── 4. Indian Devices & IP Geolocation ────────────────────────────────────
    print("Seeding Indian Devices & IP Endpoints...")
    devices: list[Device] = []
    for u in users:
        d = Device(
            id=uuid.uuid4(),
            user_id=u.id,
            device_fingerprint=f"fp_in_{u.name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}",
            user_agent="Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Mobile Safari/537.36",
            is_trusted=True,
            first_seen_at=now - timedelta(days=60),
            last_seen_at=now - timedelta(days=1),
        )
        db.add(d)
        devices.append(d)

    # Add shared suspicious device for collision testing
    collusion_device = Device(
        id=uuid.uuid4(),
        user_id=users[-1].id,
        device_fingerprint="fp_in_shared_suspicious_hw99",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 HeadlessChrome",
        is_trusted=False,
        first_seen_at=now - timedelta(days=10),
        last_seen_at=now,
    )
    db.add(collusion_device)
    devices.append(collusion_device)

    indian_ips = [
        ("103.21.124.5", "IN", "Mumbai", False, False, 0.01),
        ("49.207.180.12", "IN", "Bengaluru", False, False, 0.02),
        ("14.139.45.10", "IN", "Delhi", False, False, 0.02),
        ("122.176.54.20", "IN", "Chennai", False, False, 0.01),
        ("182.73.120.5", "IN", "Kolkata", False, False, 0.03),
        ("115.240.90.15", "IN", "Hyderabad", False, False, 0.02),
        ("27.57.180.25", "IN", "Pune", False, False, 0.01),
        ("185.220.101.5", "IN", "Tor Exit Node", True, True, 0.88),
    ]

    ip_objects: list[IPAddress] = []
    for ip_str, country, city, is_vpn, is_tor, rep in indian_ips:
        ip = IPAddress(
            id=uuid.uuid4(),
            ip_address=ip_str,
            geo_country=country,
            geo_city=city,
            is_vpn=is_vpn,
            is_tor=is_tor,
            reputation_score=rep,
            last_checked_at=now - timedelta(days=5),
        )
        db.add(ip)
        ip_objects.append(ip)

    db.flush()
    print(f"  ✓ Inserted {len(devices)} devices and {len(ip_objects)} IP geolocation nodes.")

    # ── 5. Inference & Decision Engine Setup ──────────────────────────────────
    print("\nExecuting Live ML & Rules Pipeline to Score Demo Transactions...")
    inference_svc = FraudInferenceService.get_instance()
    decision_engine = get_decision_engine()

    # Pre-crafted realistic Indian transaction scenarios
    indian_scenarios = [
        # Normal everyday transactions (UPI, NEFT, IMPS, POS)
        {"user_idx": 2, "merchant_name": "Swiggy India", "amount": 340.0, "type": "UPI", "channel": "Mobile_App", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 45000.0, "loan": 0, "emi": 0.0, "score": 760, "hour": 13, "days_ago": 0, "ip_idx": 0},
        {"user_idx": 2, "merchant_name": "D-Mart Supermarket", "amount": 2450.0, "type": "UPI", "channel": "POS_Terminal", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 44660.0, "loan": 0, "emi": 0.0, "score": 760, "hour": 18, "days_ago": 1, "ip_idx": 0},
        {"user_idx": 3, "merchant_name": "Amazon India", "amount": 1899.0, "type": "UPI", "channel": "Mobile_App", "acct": "Salary", "state": "Karnataka", "direction": "Debit", "bal": 125000.0, "loan": 1, "emi": 18500.0, "score": 810, "hour": 20, "days_ago": 1, "ip_idx": 1},
        {"user_idx": 3, "merchant_name": "Tata Power Mumbai", "amount": 3200.0, "type": "Auto_Debit", "channel": "Web", "acct": "Salary", "state": "Karnataka", "direction": "Debit", "bal": 123101.0, "loan": 1, "emi": 18500.0, "score": 810, "hour": 10, "days_ago": 2, "ip_idx": 1},
        {"user_idx": 4, "merchant_name": "IRCTC Rail Connect", "amount": 1450.0, "type": "Net_Banking", "channel": "Web", "acct": "NRI", "state": "Tamil Nadu", "direction": "Debit", "bal": 350000.0, "loan": 0, "emi": 0.0, "score": 740, "hour": 15, "days_ago": 2, "ip_idx": 3},
        {"user_idx": 4, "merchant_name": "Apollo Pharmacy", "amount": 620.0, "type": "UPI", "channel": "Mobile_App", "acct": "NRI", "state": "Tamil Nadu", "direction": "Debit", "bal": 348550.0, "loan": 0, "emi": 0.0, "score": 740, "hour": 17, "days_ago": 3, "ip_idx": 3},
        {"user_idx": 5, "merchant_name": "Reliance Digital", "amount": 42999.0, "type": "Credit_Card", "channel": "POS_Terminal", "acct": "Current", "state": "Delhi", "direction": "Debit", "bal": 680000.0, "loan": 1, "emi": 45000.0, "score": 690, "hour": 19, "days_ago": 3, "ip_idx": 2},
        {"user_idx": 5, "merchant_name": "Zerodha Broking", "amount": 50000.0, "type": "Net_Banking", "channel": "Web", "acct": "Current", "state": "Delhi", "direction": "Debit", "bal": 637001.0, "loan": 1, "emi": 45000.0, "score": 690, "hour": 11, "days_ago": 4, "ip_idx": 2},
        {"user_idx": 6, "merchant_name": "Flipkart Internet", "amount": 1249.0, "type": "UPI", "channel": "Mobile_App", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 62000.0, "loan": 0, "emi": 0.0, "score": 760, "hour": 14, "days_ago": 4, "ip_idx": 6},
        {"user_idx": 7, "merchant_name": "Zomato Payments", "amount": 480.0, "type": "UPI", "channel": "Mobile_App", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 28000.0, "loan": 1, "emi": 6200.0, "score": 620, "hour": 21, "days_ago": 5, "ip_idx": 6},
        
        # High-value legitimate salary / business credits
        {"user_idx": 3, "merchant_name": "Tata Power Mumbai", "amount": 125000.0, "type": "NEFT", "channel": "Branch", "acct": "Salary", "state": "Karnataka", "direction": "Credit", "bal": 248101.0, "loan": 1, "emi": 18500.0, "score": 810, "hour": 9, "days_ago": 6, "ip_idx": 1},
        {"user_idx": 5, "merchant_name": "Reliance Digital", "amount": 350000.0, "type": "RTGS", "channel": "Net_Banking", "acct": "Current", "state": "Delhi", "direction": "Credit", "bal": 987001.0, "loan": 1, "emi": 45000.0, "score": 690, "hour": 12, "days_ago": 7, "ip_idx": 2},

        # Suspicious / High-risk scenarios
        # 1. Nocturnal high-value transfer via Tor / VPN
        {"user_idx": 7, "merchant_name": "Unknown P2P Crypto Gateway", "amount": 185000.0, "type": "IMPS", "channel": "Web", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 190000.0, "loan": 1, "emi": 6200.0, "score": 620, "hour": 3, "days_ago": 0, "ip_idx": 7, "is_anom": True},
        # 2. Huge amount spike with rapid velocity on jewellery
        {"user_idx": 2, "merchant_name": "Tanishq Jewellery", "amount": 285000.0, "type": "UPI", "channel": "Mobile_App", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 290000.0, "loan": 0, "emi": 0.0, "score": 760, "hour": 2, "days_ago": 1, "ip_idx": 0, "is_anom": True},
        # 3. Sudden balance drain via international channel
        {"user_idx": 6, "merchant_name": "Unknown P2P Crypto Gateway", "amount": 58000.0, "type": "Net_Banking", "channel": "API", "acct": "Savings", "state": "Maharashtra", "direction": "Debit", "bal": 60000.0, "loan": 0, "emi": 0.0, "score": 760, "hour": 4, "days_ago": 2, "ip_idx": 7, "is_anom": True},
    ]

    # Expand scenarios into a rich, realistic distribution of ~50 transactions
    all_scenarios = list(indian_scenarios)
    for i in range(35):
        base = rng.choice(indian_scenarios[:10])
        mutated = dict(base)
        mutated["amount"] = round(base["amount"] * rng.uniform(0.7, 1.8), 2)
        mutated["days_ago"] = rng.randint(0, 30)
        mutated["hour"] = rng.randint(8, 22)
        all_scenarios.append(mutated)

    inserted_txns = 0
    inserted_alerts = 0
    merchant_by_name = {m.name: m for m in merchants}

    for sc in all_scenarios:
        user = users[sc["user_idx"]]
        merch = merchant_by_name[sc["merchant_name"]]
        device = devices[sc["user_idx"]]
        ip_obj = ip_objects[sc["ip_idx"]]
        ts = now - timedelta(days=sc["days_ago"], hours=rng.randint(0, 5), minutes=rng.randint(0, 59))

        # Build inference payload for real ML model
        payload = {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "customer_id": f"CUST_{user.email.split('@')[0]}",
            "transaction_amount": sc["amount"],
            "amount": sc["amount"],
            "account_balance": sc["bal"],
            "credit_score": sc["score"],
            "has_loan": sc["loan"],
            "loan_type": "Personal" if sc["loan"] else "None",
            "emi_amount": sc["emi"],
            "transaction_hour": sc["hour"],
            "account_type": sc["acct"],
            "transaction_type": sc["type"],
            "transaction_direction": sc["direction"],
            "merchant_category": merch.category,
            "state": sc["state"],
            "channel": sc["channel"],
            "kyc_status": "Verified",
            "transaction_status": "Success",
        }

        # 1. Run live ML model inference
        ml_res = inference_svc.predict(payload)
        fraud_score = ml_res.fraud_probability
        risk_level_str = ml_res.risk_level
        shap_values = ml_res.shap_drivers or []
        latency_ms = ml_res.latency_ms

        # 2. Run live Decision Engine
        d_ctx = DecisionContext(
            fraud_score=fraud_score,
            amount=sc["amount"],
            currency="INR",
            merchant=merch.name,
            category=merch.category,
            country="IN",
            realtime_features={
                "hour_of_day": sc["hour"],
                "velocity_1m": 6 if sc.get("is_anom") else 1,
                "velocity_5m": 14 if sc.get("is_anom") else 2,
                "failed_auth_5m": 3 if sc.get("is_anom") else 0,
                "is_unusual_hour": sc["hour"] < 6 or sc["hour"] >= 23,
                "amount_deviation_ratio": 5.2 if sc.get("is_anom") else 1.0,
            },
            graph_risk={
                "graph_risk_score": 0.72 if sc.get("is_anom") else 0.05,
                "graph_shared_device_users": 4 if sc.get("is_anom") else 1,
            },
        )
        dec_res = decision_engine.evaluate(d_ctx)
        final_decision_str = dec_res.decision.value
        is_fraud = final_decision_str == "BLOCK" or fraud_score >= 0.65

        # 3. Insert Transaction
        txn = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            merchant_id=merch.id,
            device_id=device.id,
            ip_id=ip_obj.id,
            transaction_ref=payload["transaction_id"],
            amount=sc["amount"],
            transaction_amount=sc["amount"],
            currency="INR",
            merchant=merch.name,
            category=merch.category,
            country="IN",
            customer_id=payload["customer_id"],
            account_type=sc["acct"],
            transaction_type=sc["type"],
            transaction_direction=sc["direction"],
            account_balance=sc["bal"],
            merchant_category=merch.category,
            state=sc["state"],
            credit_score=sc["score"],
            has_loan=sc["loan"],
            loan_type="Personal" if sc["loan"] else "None",
            emi_amount=sc["emi"],
            transaction_status="Completed" if not is_fraud else "Flagged",
            channel=sc["channel"],
            kyc_status="Verified",
            transaction_hour=sc["hour"],
            transaction_date=ts.strftime("%Y-%m-%d"),
            transaction_time=ts.strftime("%H:%M:%S"),
            fraud_score=round(fraud_score, 4),
            risk_level=RiskLevel(risk_level_str),
            is_fraud=is_fraud,
            label=int(is_fraud),
            timestamp=ts,
        )
        db.add(txn)
        inserted_txns += 1

        # 4. Insert FraudPrediction
        pred = FraudPrediction(
            id=uuid.uuid4(),
            transaction_id=txn.id,
            model_id=banking_model_meta.id,
            endpoint="/predict/transaction",
            input_hash=uuid.uuid4().hex[:16],
            fraud_score=round(fraud_score, 4),
            risk_level=RiskLevel(risk_level_str),
            is_fraud=is_fraud,
            decision=DecisionType(final_decision_str),
            shap_values=shap_values,
            latency_ms=latency_ms,
            model_version="2.0.0",
            created_at=ts,
        )
        db.add(pred)

        # 5. Insert Genuine Alert if flagged
        if final_decision_str in ("BLOCK", "REVIEW") or fraud_score >= 0.50:
            alert = FraudAlert(
                id=uuid.uuid4(),
                user_id=user.id,
                transaction_id=txn.id,
                prediction_id=pred.id,
                assigned_to=analyst_user.id,
                alert_type="banking_fraud",
                risk_level=RiskLevel(risk_level_str),
                score=round(fraud_score, 4),
                description=f"Automated risk alert on {txn.transaction_type} of ₹{txn.amount:,.2f} via {txn.channel} at {txn.merchant} ({dec_res.primary_reason})",
                status=AlertStatus.OPEN if sc["days_ago"] == 0 else AlertStatus.REVIEWED,
                shap_values=shap_values,
                metadata_={
                    "merchant": merch.name,
                    "amount": txn.amount,
                    "currency": "INR",
                    "state": txn.state,
                    "decision": final_decision_str,
                },
                created_at=ts,
                resolved_at=ts + timedelta(hours=3) if sc["days_ago"] > 0 else None,
            )
            db.add(alert)
            inserted_alerts += 1

    # ── 6. Seed Behavioral Telemetry Sessions ────────────────────────────────
    print("Seeding Indian Behavioral Telemetry Sessions...")
    inserted_behavior = 0
    for u in users:
        for _ in range(3):
            b_log = BehaviorLog(
                id=uuid.uuid4(),
                user_id=u.id,
                session_id=f"sess_in_{uuid.uuid4().hex[:12]}",
                ip_address=rng.choice(indian_ips)[0],
                geo_country="IN",
                geo_city=rng.choice(["Mumbai", "Bengaluru", "Delhi", "Chennai", "Pune", "Hyderabad"]),
                is_vpn=False,
                is_tor=False,
                typing_speed=round(rng.uniform(4.2, 7.5), 2),
                mouse_velocity=round(rng.uniform(120.0, 380.0), 2),
                login_hour=rng.randint(9, 21),
                failed_logins=0,
                device_change=False,
                anomaly_score=round(rng.uniform(0.01, 0.15), 4),
                risk_level=RiskLevel.LOW,
                created_at=now - timedelta(days=rng.randint(0, 15), hours=rng.randint(0, 23)),
            )
            db.add(b_log)
            inserted_behavior += 1

    # ── 7. Audit Log ─────────────────────────────────────────────────────────
    audit = AuditLog(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        action="DATABASE_STANDARDIZED_INDIA",
        entity_type="SYSTEM",
        entity_id=str(admin_user.id),
        details={"currency": "INR", "country": "IN", "locale": "en-IN", "status": "Cleaned & Reseeded"},
        ip_address="103.21.124.5",
        created_at=now,
    )
    db.add(audit)

    db.commit()
    print(f"\nSeeding Complete!")
    print(f"  ✓ Total Transactions Created: {inserted_txns}")
    print(f"  ✓ Total Genuine Alerts Created: {inserted_alerts}")
    print(f"  ✓ Total Behavior Sessions Created: {inserted_behavior}")


def flush_redis_cache():
    print("\n========================================================")
    print("STEP 3: FLUSHING REDIS CACHE & FEATURE STORE")
    print("========================================================")
    try:
        r = get_redis_client()
        r.flushdb()
        print("  ✓ Redis cache flushed successfully.")
    except Exception as exc:
        print(f"  ⚠ Redis flush warning: {exc}")


def verify_database(db: Session):
    print("\n========================================================")
    print("STEP 4: VERIFYING DATABASE COUNTS & CONSISTENCY")
    print("========================================================")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    for t in tables:
        count = db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
        print(f"  • {t}: {count} rows")


def main():
    db = SessionLocal()
    try:
        clean_database(db)
        reseed_indian_demo_data(db)
        flush_redis_cache()
        verify_database(db)
        print("\nAll database cleanup and Indian standardization steps completed successfully!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
