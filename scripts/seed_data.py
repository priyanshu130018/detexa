"""
scripts/seed_data.py
─────────────────────────────────────────────────────────────────────────────
Populate the database with realistic demo data so the dashboard is
immediately useful after a fresh install.

    python scripts/seed_data.py
"""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from faker import Faker
from sqlalchemy.orm import Session

from core.config import settings
from core.security import hash_password
from database.db import engine, SessionLocal
from database.models import (
    Base, User, Transaction, BehaviorLog, Alert, PredictionLog,
    RiskLevel, AlertStatus,
)

fake = Faker()
rng = random.Random(42)


def risk_from_score(score: float) -> RiskLevel:
    if score >= settings.high_risk_threshold:
        return RiskLevel.HIGH
    if score >= settings.fraud_threshold:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def seed(db: Session, n_users: int = 10, n_txns: int = 500):
    print("Creating tables …")
    Base.metadata.create_all(bind=engine)

    # Check if already seeded
    if db.query(User).filter(User.email == "admin@detexa.io").first():
        print("Database already seeded (admin user exists). Skipping.")
        return

    # ── Users ─────────────────────────────────────────────────────────────────
    print(f"Seeding {n_users} users …")
    users = []
    # Admin user
    admin = User(
        id=uuid.uuid4(),
        name="Admin User",
        email="admin@detexa.io",
        mobile="+1-555-000-0001",
        hashed_password=hash_password("Admin@1234"),
        is_admin=True,
    )
    db.add(admin)
    users.append(admin)

    for _ in range(n_users - 1):
        u = User(
            id=uuid.uuid4(),
            name=fake.name(),
            email=fake.unique.email(),
            mobile=fake.phone_number()[:20],
            hashed_password=hash_password("Test@1234"),
        )
        db.add(u)
        users.append(u)

    db.commit()

    # ── Transactions ──────────────────────────────────────────────────────────
    print(f"Seeding {n_txns} transactions …")
    merchants = ["Amazon", "Netflix", "Uber", "Walmart", "Apple", "Google",
                 "Steam", "Airbnb", "Spotify", "Target"]
    categories = ["electronics", "entertainment", "travel", "food",
                  "clothing", "health", "gaming"]
    countries = ["US", "GB", "IN", "DE", "FR", "CA", "AU", "SG"]

    now = datetime.now(timezone.utc)
    transactions = []
    for i in range(n_txns):
        user = rng.choice(users)
        score = rng.betavariate(1, 9) if rng.random() > 0.017 else rng.betavariate(8, 2)
        risk = risk_from_score(score)
        is_fraud = score >= settings.fraud_threshold
        days_ago = rng.randint(0, 90)
        ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86400))

        txn = Transaction(
            id=uuid.uuid4(),
            user_id=user.id,
            transaction_ref=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            amount=round(rng.lognormvariate(3, 1.5), 2),
            v1=rng.gauss(0, 1), v2=rng.gauss(0, 1), v3=rng.gauss(0, 1),
            v4=rng.gauss(0, 1), v5=rng.gauss(0, 1), v6=rng.gauss(0, 1),
            v7=rng.gauss(0, 1), v8=rng.gauss(0, 1), v9=rng.gauss(0, 1),
            v10=rng.gauss(0, 1), v11=rng.gauss(0, 1), v12=rng.gauss(0, 1),
            v13=rng.gauss(0, 1), v14=rng.gauss(0, 1), v15=rng.gauss(0, 1),
            v16=rng.gauss(0, 1), v17=rng.gauss(0, 1), v18=rng.gauss(0, 1),
            v19=rng.gauss(0, 1), v20=rng.gauss(0, 1), v21=rng.gauss(0, 1),
            v22=rng.gauss(0, 1), v23=rng.gauss(0, 1), v24=rng.gauss(0, 1),
            v25=rng.gauss(0, 1), v26=rng.gauss(0, 1), v27=rng.gauss(0, 1),
            v28=rng.gauss(0, 1),
            merchant=rng.choice(merchants),
            category=rng.choice(categories),
            country=rng.choice(countries),
            fraud_score=round(score, 4),
            risk_level=risk,
            is_fraud=is_fraud,
            label=int(is_fraud),
            timestamp=ts,
        )
        db.add(txn)
        transactions.append(txn)

        if is_fraud or score > 0.6:
            alert = Alert(
                id=uuid.uuid4(),
                user_id=user.id,
                transaction_id=txn.id,
                alert_type="credit_fraud",
                risk_level=risk,
                score=round(score, 4),
                description=f"Suspicious transaction of ${txn.amount:.2f} at {txn.merchant}",
                status=rng.choice(list(AlertStatus)),
                created_at=ts,
            )
            db.add(alert)

    db.commit()

    # ── Behaviour Logs ────────────────────────────────────────────────────────
    print("Seeding behaviour logs …")
    countries_list = ["US", "IN", "DE", "RU", "CN", "BR"]
    for _ in range(200):
        user = rng.choice(users)
        score = rng.betavariate(1, 6)
        risk = risk_from_score(score)
        days_ago = rng.randint(0, 30)
        ts = now - timedelta(days=days_ago, seconds=rng.randint(0, 86400))

        bl = BehaviorLog(
            id=uuid.uuid4(),
            user_id=user.id,
            session_id=uuid.uuid4().hex,
            ip_address=fake.ipv4(),
            device_fingerprint=uuid.uuid4().hex,
            user_agent=fake.user_agent(),
            login_hour=rng.randint(0, 23),
            typing_speed=round(rng.uniform(1, 10), 2),
            mouse_velocity=round(rng.uniform(50, 500), 2),
            geo_country=rng.choice(countries_list),
            geo_city=fake.city(),
            is_vpn=rng.random() < 0.08,
            is_tor=rng.random() < 0.02,
            failed_logins=rng.randint(0, 5),
            device_change=rng.random() < 0.1,
            anomaly_score=round(score, 4),
            risk_level=risk,
            created_at=ts,
        )
        db.add(bl)

        if score > 0.6:
            alert = Alert(
                id=uuid.uuid4(),
                user_id=user.id,
                alert_type="behavior_anomaly",
                risk_level=risk,
                score=round(score, 4),
                description=f"Anomalous login from {bl.geo_country} via {'TOR' if bl.is_tor else 'VPN' if bl.is_vpn else 'unknown device'}",
                status=AlertStatus.OPEN,
                created_at=ts,
            )
            db.add(alert)

    db.commit()
    print("✓ Seed data inserted successfully")
    print(f"  Admin login: admin@detexa.io / Admin@1234")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
