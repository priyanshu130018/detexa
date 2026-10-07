"""
scripts/seed_data.py
─────────────────────────────────────────────────────────────────────────────
Populate the normalized Neon PostgreSQL database with realistic demonstration
data across all 10 entities for immediate UI exploration.
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
    credit_model_meta = ModelMetadata(
        id=uuid.uuid4(),
        model_name="CreditFraudEnsemble",
        version="1.0.0",
        algorithm="XGBoost + LightGBM + LogisticRegression Stacking",
        threshold=settings.fraud_threshold,
        is_active=True,
        metrics={"auc_pr": 0.884, "f1_score": 0.862, "precision": 0.895, "recall": 0.831},
        trained_at=now - timedelta(days=90),
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
    db.add(credit_model_meta)
    db.add(behavior_model_meta)
    db.flush()

    # ── 2. Merchants ─────────────────────────────────────────────────────────
    print("Seeding Merchants...")
    merchant_defs = [
        ("Amazon", "ecommerce", 0.05),
        ("Netflix", "entertainment", 0.02),
        ("Uber", "rideshare", 0.12),
        ("Walmart", "retail", 0.04),
        ("Apple", "electronics", 0.06),
        ("Google", "digital_services", 0.03),
        ("Steam", "gaming", 0.15),
        ("Airbnb", "travel", 0.18),
        ("Spotify", "entertainment", 0.02),
        ("Target", "retail", 0.04),
        ("BestBuy", "electronics", 0.09),
        ("Delta Airlines", "airlines", 0.14),
        ("CryptoExchangeX", "financial_crypto", 0.45),
        ("LuxuryJewelers", "luxury_goods", 0.38),
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
        mobile="+1-555-000-0001",
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
        name="Sarah Analyst",
        email="analyst@detexa.io",
        mobile="+1-555-000-0002",
        hashed_password=hash_password("Analyst@1234"),
        is_admin=False,
        is_active=True,
        created_at=now - timedelta(days=120),
        last_login=now - timedelta(hours=2),
    )
    db.add(analyst)
    users.append(analyst)

    for _ in range(n_users - 2):
        u = User(
            id=uuid.uuid4(),
            name=fake.name(),
            email=fake.unique.email().lower(),
            mobile=fake.phone_number()[:20],
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
        # Each user has 1-2 devices
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
        ("US", "New York", False, False, 0.0),
        ("US", "San Francisco", False, False, 0.0),
        ("GB", "London", False, False, 0.05),
        ("IN", "Bengaluru", False, False, 0.02),
        ("DE", "Frankfurt", False, False, 0.02),
        ("SG", "Singapore", False, False, 0.04),
        ("RU", "Moscow", True, False, 0.65),
        ("CN", "Shanghai", True, False, 0.50),
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
    print(f"Seeding {n_txns} transactions with predictions and alerts...")
    for _ in range(n_txns):
        user = rng.choice(users)
        merchant = rng.choice(merchants)
        device = rng.choice([d for d in devices if d.user_id == user.id] or devices)
        ip_obj = rng.choice(ip_addresses)

        # Rare high risk spikes vs normal beta distribution
        score = rng.betavariate(1, 9) if rng.random() > 0.04 else rng.betavariate(8, 2)
        if merchant.risk_score > 0.3:
            score = min(1.0, score + rng.uniform(0.1, 0.3))

        risk = risk_from_score(score)
        decision = decision_from_score(score)
        is_fraud = score >= settings.fraud_threshold
        days_ago = rng.randint(0, 60)
        ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86400))
        amt = round(rng.lognormvariate(3.2, 1.4), 2)
        if amt < 1.0:
            amt = 1.0

        txn = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            merchant_id=merchant.id,
            device_id=device.id,
            ip_id=ip_obj.id,
            transaction_ref=f"TXN-{uuid.uuid4().hex[:10].upper()}",
            amount=amt,
            currency="USD",
            merchant=merchant.name,
            category=merchant.category,
            country=ip_obj.geo_country or "US",
            fraud_score=round(score, 4),
            risk_level=risk,
            is_fraud=is_fraud,
            label=int(is_fraud),
            timestamp=ts,
        )
        for v_i in range(1, 29):
            setattr(txn, f"v{v_i}", rng.gauss(0, 1))

        db.add(txn)
        db.flush()

        shap_list = [
            {"feature": "V14", "shap_value": round(rng.uniform(0.1, 0.5), 4)},
            {"feature": "Amount", "shap_value": round(rng.uniform(0.05, 0.3), 4)},
            {"feature": "V4", "shap_value": round(rng.uniform(-0.1, 0.2), 4)},
            {"feature": "V10", "shap_value": round(rng.uniform(0.01, 0.15), 4)},
        ]

        pred = FraudPrediction(
            id=uuid.uuid4(),
            transaction_id=txn.id,
            model_id=credit_model_meta.id,
            endpoint="/predict/credit",
            input_hash=uuid.uuid4().hex[:16],
            fraud_score=round(score, 4),
            anomaly_score=None,
            risk_level=risk,
            is_fraud=is_fraud,
            decision=decision,
            shap_values=shap_list,
            latency_ms=round(rng.uniform(12.0, 48.0), 2),
            model_version="1.0.0",
            created_at=ts,
        )
        db.add(pred)
        db.flush()

        if is_fraud or score >= 0.45:
            alert = FraudAlert(
                id=uuid.uuid4(),
                user_id=user.id,
                transaction_id=txn.id,
                prediction_id=pred.id,
                assigned_to=analyst.id if rng.random() > 0.4 else None,
                alert_type="credit_fraud",
                risk_level=risk,
                score=round(score, 4),
                description=f"Suspicious card charge of ${txn.amount:.2f} at {txn.merchant} [Score: {score:.2f}]",
                status=rng.choice(list(AlertStatus)),
                shap_values=shap_list,
                metadata_={
                    "merchant": merchant.name,
                    "amount": txn.amount,
                    "currency": txn.currency,
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
        is_anomalous = score >= settings.fraud_threshold
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
        ("MODEL_LOADED", "model", str(credit_model_meta.id), {"version": "1.0.0"}),
        ("MODEL_LOADED", "model", str(behavior_model_meta.id), {"version": "1.0.0"}),
        ("SECURITY_RULE_EVALUATED", "system", "rule_engine", {"rules_active": 12}),
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
    print("✅ Normalized database successfully seeded across all 10 tables!")
    print("   Admin credentials:   admin@detexa.io   / Admin@1234")
    print("   Analyst credentials: analyst@detexa.io / Analyst@1234")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed(db_session)
    finally:
        db_session.close()
