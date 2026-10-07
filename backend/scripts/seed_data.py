"""
scripts/seed_data.py
─────────────────────────────────────────────────────────────────────────────
Populate the normalized PostgreSQL database with realistic demonstration
data across all entities for the Indian Banking Fraud platform.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import sys
import uuid

# Enable importing app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, SessionLocal
from app.db.base import (
    Base,
    User,
    Merchant,
    Device,
    IPAddress,
    ModelMetadata,
    Transaction,
    FraudPrediction,
    FraudAlert,
    BehaviorLog,
    AuditLog,
    RiskLevel,
    AlertStatus,
    DecisionType,
)

fake = Faker()
rng = random.Random(42)

INDIAN_STATES = [
    "Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "Telangana",
    "Gujarat", "Uttar Pradesh", "West Bengal", "Rajasthan", "Kerala"
]
ACCOUNT_TYPES = ["Savings", "Current", "Salary"]
TRANSACTION_TYPES = ["UPI", "NEFT", "IMPS", "RTGS", "Debit Card", "Credit Card", "Net Banking"]
TRANSACTION_DIRECTIONS = ["Debit", "Credit"]
MERCHANT_CATEGORIES = ["Electronics", "Jewellery", "Grocery", "Travel", "Dining", "Apparel", "Utilities", "Entertainment"]
CHANNELS = ["Mobile Banking", "Net Banking", "ATM", "Branch", "POS"]
KYC_STATUSES = ["Verified", "Pending", "Non-Verified"]
LOAN_TYPES = ["None", "Personal", "Home", "Auto", "Education"]


def risk_from_score(score: float) -> RiskLevel:
    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH
    if score >= settings.fraud_threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def decision_from_score(score: float) -> DecisionType:
    if score >= settings.high_risk_threshold:
        return DecisionType.BLOCK
    if score >= settings.fraud_threshold:
        return DecisionType.REVIEW
    if score >= 0.40:
        return DecisionType.CHALLENGE
    return DecisionType.ALLOW


def seed(db: Session, n_users: int = 12, n_txns: int = 500, n_behavior: int = 200):
    print("Verifying schema state...")
    Base.metadata.create_all(bind=engine)

    if db.query(User).filter(User.email == "admin@detexa.io").first():
        print("Database is already seeded with admin user. Skipping duplicate seed.")
        return

    now = datetime.now(timezone.utc)

    # ── 1. Model Metadata ────────────────────────────────────────────────────
    print("Seeding ML Model Registry Metadata...")
    banking_model_meta = ModelMetadata(
        id=uuid.uuid4(),
        model_name="BankingFraudXGBoost",
        version="2.0.0",
        algorithm="XGBoost Classifier + Native TreeSHAP",
        threshold=settings.fraud_threshold,
        is_active=True,
        metrics={"roc_auc": 0.528, "f1_score": 0.0824, "precision": 0.0789, "recall": 0.0862, "optimal_threshold": 0.65},
        trained_at=now - timedelta(days=5),
    )
    behavior_model_meta = ModelMetadata(
        id=uuid.uuid4(),
        model_name="BehaviorAnomalyModel",
        version="1.0.0",
        algorithm="Isolation Forest + Heuristic Anomaly Scoring",
        threshold=settings.fraud_threshold,
        is_active=True,
        metrics={"contamination": 0.05, "n_estimators": 100},
        trained_at=now - timedelta(days=90),
    )
    db.add(banking_model_meta)
    db.add(behavior_model_meta)
    db.flush()

    # ── 2. Merchants ─────────────────────────────────────────────────────────
    print("Seeding Merchants...")
    merchant_defs = [
        ("Flipkart India", "Electronics", 0.05),
        ("Amazon India", "Electronics", 0.04),
        ("Swiggy", "Dining", 0.02),
        ("Zomato", "Dining", 0.02),
        ("Tanishq Jewellery", "Jewellery", 0.35),
        ("Kalyan Jewellers", "Jewellery", 0.38),
        ("Reliance Digital", "Electronics", 0.06),
        ("Croma", "Electronics", 0.07),
        ("MakeMyTrip", "Travel", 0.12),
        ("IRCTC", "Travel", 0.03),
        ("BigBasket", "Grocery", 0.02),
        ("Blinkit", "Grocery", 0.03),
        ("CryptoExchange IN", "Digital Assets", 0.48),
        ("Myntra", "Apparel", 0.04),
    ]
    merchants: list[Merchant] = []
    for name, cat, risk_s in merchant_defs:
        m = Merchant(
            id=uuid.uuid4(),
            name=name,
            category=cat,
            risk_score=risk_s,
            created_at=now - timedelta(days=120),
        )
        db.add(m)
        merchants.append(m)
    db.flush()

    # ── 3. Users ─────────────────────────────────────────────────────────────
    print(f"Seeding {n_users} users...")
    users: list[User] = []

    admin = User(
        id=uuid.uuid4(),
        name="Admin User",
        email="admin@detexa.io",
        mobile="+91-9876543210",
        hashed_password=hash_password("Admin@1234"),
        is_admin=True,
        is_active=True,
        created_at=now - timedelta(days=180),
        last_login=now - timedelta(minutes=5),
    )
    db.add(admin)
    users.append(admin)

    analyst = User(
        id=uuid.uuid4(),
        name="Priya Analyst",
        email="analyst@detexa.io",
        mobile="+91-9876543211",
        hashed_password=hash_password("Analyst@1234"),
        is_admin=False,
        is_active=True,
        created_at=now - timedelta(days=120),
        last_login=now - timedelta(hours=2),
    )
    db.add(analyst)
    users.append(analyst)

    for i in range(n_users - 2):
        u = User(
            id=uuid.uuid4(),
            name=fake.name(),
            email=fake.unique.email().lower(),
            mobile=f"+91-98{rng.randint(10000000, 99999999)}",
            hashed_password=hash_password("Test@1234"),
            is_admin=False,
            is_active=True,
            created_at=now - timedelta(days=rng.randint(10, 150)),
            last_login=now - timedelta(hours=rng.randint(1, 72)),
        )
        db.add(u)
        users.append(u)
    db.flush()

    # ── 4. Devices & IP Addresses ────────────────────────────────────────────
    print("Seeding Devices & IP Addresses...")
    devices: list[Device] = []
    for u in users:
        for _ in range(rng.randint(1, 2)):
            d = Device(
                id=uuid.uuid4(),
                user_id=u.id,
                device_fingerprint=uuid.uuid4().hex[:24],
                user_agent=fake.user_agent(),
                is_trusted=rng.random() > 0.10,
                first_seen_at=now - timedelta(days=rng.randint(30, 180)),
                last_seen_at=now - timedelta(days=rng.randint(0, 15)),
            )
            db.add(d)
            devices.append(d)

    geo_locations = [
        ("IN", "Mumbai", False, False, 0.01),
        ("IN", "Bengaluru", False, False, 0.02),
        ("IN", "Delhi", False, False, 0.02),
        ("IN", "Hyderabad", False, False, 0.02),
        ("IN", "Chennai", False, False, 0.01),
        ("IN", "Pune", False, False, 0.01),
        ("IN", "Kolkata", False, False, 0.03),
        ("RU", "Moscow", True, False, 0.65),
        ("NL", "Amsterdam", True, True, 0.85),
    ]
    ip_addresses: list[IPAddress] = []
    for country, city, vpn, tor, rep in geo_locations:
        for _ in range(3):
            ip = IPAddress(
                id=uuid.uuid4(),
                ip_address=fake.ipv4(),
                geo_country=country,
                geo_city=city,
                is_vpn=vpn,
                is_tor=tor,
                reputation_score=rep,
                last_checked_at=now - timedelta(days=rng.randint(0, 30)),
            )
            db.add(ip)
            ip_addresses.append(ip)
    db.flush()

    # ── 5. Transactions, Predictions, & Alerts ───────────────────────────────
    print(f"Seeding {n_txns} Indian banking transactions with predictions and alerts...")
    for i in range(n_txns):
        user = rng.choice(users)
        merchant = rng.choice(merchants)
        device = rng.choice([d for d in devices if d.user_id == user.id] or devices)
        ip_obj = rng.choice(ip_addresses)

        score = rng.betavariate(1, 9) if rng.random() > 0.05 else rng.betavariate(7, 3)
        if merchant.risk_score > 0.3:
            score = min(1.0, score + rng.uniform(0.1, 0.25))

        risk = risk_from_score(score)
        decision = decision_from_score(score)
        is_fraud = score >= 0.65
        days_ago = rng.randint(0, 60)
        ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86400))
        amt = round(rng.lognormvariate(8.0, 1.2), 2)
        if amt < 10.0:
            amt = 10.0

        acct_bal = round(rng.uniform(5000.0, 500000.0), 2)
        has_loan_val = rng.random() < 0.35
        loan_type_val = rng.choice(LOAN_TYPES[1:]) if has_loan_val else "None"
        emi_val = round(rng.uniform(2000.0, 35000.0), 2) if has_loan_val else 0.0

        txn = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            merchant_id=merchant.id,
            device_id=device.id,
            ip_id=ip_obj.id,
            transaction_ref=f"TXN-{uuid.uuid4().hex[:10].upper()}",
            amount=amt,
            currency="INR",
            merchant=merchant.name,
            category=merchant.category,
            country=ip_obj.geo_country or "IN",
            customer_id=f"CUST_{rng.randint(10000, 99999)}",
            account_type=rng.choice(ACCOUNT_TYPES),
            transaction_type=rng.choice(TRANSACTION_TYPES),
            transaction_direction=rng.choice(TRANSACTION_DIRECTIONS),
            account_balance=acct_bal,
            merchant_category=merchant.category,
            state=rng.choice(INDIAN_STATES),
            credit_score=rng.randint(550, 850),
            has_loan=has_loan_val,
            loan_type=loan_type_val,
            emi_amount=emi_val,
            transaction_status="Completed" if not is_fraud else "Flagged",
            channel=rng.choice(CHANNELS),
            kyc_status=rng.choice(KYC_STATUSES),
            transaction_hour=ts.hour,
            transaction_date=ts.strftime("%Y-%m-%d"),
            transaction_time=ts.strftime("%H:%M:%S"),
            fraud_score=round(score, 4),
            risk_level=risk,
            is_fraud=is_fraud,
            label=int(is_fraud),
            timestamp=ts,
        )
        db.add(txn)
        db.flush()

        shap_list = [
            {"feature": "amount_to_balance_ratio", "shap_value": round(rng.uniform(0.1, 0.4), 4), "direction": "RISK_INCREASING"},
            {"feature": "transaction_amount", "shap_value": round(rng.uniform(0.05, 0.3), 4), "direction": "RISK_INCREASING"},
            {"feature": "credit_score", "shap_value": round(rng.uniform(-0.2, 0.1), 4), "direction": "RISK_DECREASING"},
            {"feature": "account_balance", "shap_value": round(rng.uniform(-0.15, 0.05), 4), "direction": "RISK_DECREASING"},
        ]

        pred = FraudPrediction(
            id=uuid.uuid4(),
            transaction_id=txn.id,
            model_id=banking_model_meta.id,
            endpoint="/predict/transaction",
            input_hash=uuid.uuid4().hex[:16],
            fraud_score=round(score, 4),
            anomaly_score=None,
            risk_level=risk,
            is_fraud=is_fraud,
            decision=decision,
            shap_values=shap_list,
            latency_ms=round(rng.uniform(1.0, 5.0), 2),
            model_version="2.0.0",
            created_at=ts,
        )
        db.add(pred)
        db.flush()

        if is_fraud or score >= 0.55:
            alert = FraudAlert(
                id=uuid.uuid4(),
                user_id=user.id,
                transaction_id=txn.id,
                prediction_id=pred.id,
                assigned_to=analyst.id if rng.random() > 0.4 else None,
                alert_type="banking_fraud",
                risk_level=risk,
                score=round(score, 4),
                description=f"Suspicious banking transaction of INR {txn.amount:,.2f} via {txn.channel} ({txn.transaction_type}) [Score: {score:.2f}]",
                status=rng.choice(list(AlertStatus)),
                shap_values=shap_list,
                metadata_={
                    "merchant": merchant.name,
                    "amount": txn.amount,
                    "currency": txn.currency,
                    "customer_id": txn.customer_id,
                    "decision": decision.value,
                },
                created_at=ts,
                resolved_at=ts + timedelta(hours=rng.randint(1, 24)) if rng.random() > 0.6 else None,
            )
            db.add(alert)

    # ── 6. Behavioral Sessions ───────────────────────────────────────────────
    print(f"Seeding {n_behavior} behavioral session logs...")
    for _ in range(n_behavior):
        user = rng.choice(users)
        device = rng.choice([d for d in devices if d.user_id == user.id] or devices)
        ip_obj = rng.choice(ip_addresses)

        score = rng.betavariate(1, 6)
        if ip_obj.is_vpn or ip_obj.is_tor:
            score = min(1.0, score + rng.uniform(0.3, 0.5))

        risk = risk_from_score(score)
        decision = decision_from_score(score)
        days_ago = rng.randint(0, 30)
        ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86400))

        failed_logins = rng.randint(0, 5) if rng.random() < 0.15 else 0
        device_change = rng.random() < 0.12

        bl = BehaviorLog(
            id=uuid.uuid4(),
            user_id=user.id,
            device_id=device.id,
            ip_id=ip_obj.id,
            session_id=uuid.uuid4().hex[:16],
            ip_address=ip_obj.ip_address,
            device_fingerprint=device.device_fingerprint,
            user_agent=device.user_agent,
            login_hour=rng.randint(0, 23),
            typing_speed=round(rng.uniform(1.5, 9.0), 2),
            mouse_velocity=round(rng.uniform(60, 450), 2),
            geo_country=ip_obj.geo_country,
            geo_city=ip_obj.geo_city,
            is_vpn=ip_obj.is_vpn,
            is_tor=ip_obj.is_tor,
            failed_logins=failed_logins,
            device_change=device_change,
            anomaly_score=round(score, 4),
            risk_level=risk,
            created_at=ts,
        )
        db.add(bl)

        if score >= 0.55:
            factors = []
            if ip_obj.is_tor: factors.append("TOR Exit Node")
            if ip_obj.is_vpn: factors.append("VPN Connection")
            if device_change: factors.append("Unrecognized Device")
            if failed_logins >= 3: factors.append(f"{failed_logins} Failed Login Attempts")

            alert = FraudAlert(
                id=uuid.uuid4(),
                user_id=user.id,
                transaction_id=None,
                prediction_id=None,
                assigned_to=analyst.id if rng.random() > 0.5 else None,
                alert_type="behavior_anomaly",
                risk_level=risk,
                score=round(score, 4),
                description=f"Anomalous session from {bl.geo_country} ({', '.join(factors) if factors else 'Behavioral Anomaly'})",
                status=rng.choice(list(AlertStatus)),
                metadata_={"risk_factors": factors, "session_id": bl.session_id, "decision": decision.value},
                created_at=ts,
            )
            db.add(alert)

    # ── 7. Audit Logs ────────────────────────────────────────────────────────
    print("Seeding Audit Logs...")
    audit_entries = [
        ("USER_LOGIN", "user", str(admin.id), {"action": "Administrator logged in"}),
        ("USER_LOGIN", "user", str(analyst.id), {"action": "Analyst logged in"}),
        ("MODEL_LOADED", "model", str(banking_model_meta.id), {"version": "2.0.0"}),
        ("MODEL_LOADED", "model", str(behavior_model_meta.id), {"version": "1.0.0"}),
        ("SECURITY_RULE_EVALUATED", "system", "rule_engine", {"rules_active": 15}),
    ]
    for action, entity_type, entity_id, details in audit_entries:
        audit = AuditLog(
            id=uuid.uuid4(),
            user_id=admin.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address="127.0.0.1",
            details=details,
            created_at=now - timedelta(hours=rng.randint(1, 48)),
        )
        db.add(audit)

    db.commit()
    print("✅ Normalized database successfully seeded across all tables!")
    print("   Admin credentials:   admin@detexa.io   / Admin@1234")
    print("   Analyst credentials: analyst@detexa.io / Analyst@1234")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed(db_session)
    finally:
        db_session.close()
