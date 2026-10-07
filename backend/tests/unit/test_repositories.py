"""
backend/tests/unit/test_repositories.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for data access repositories.
"""

import pytest
import uuid
from datetime import datetime, timezone
from app.db.models import User, Transaction, FraudAlert, AlertStatus, RiskLevel
from app.repositories.user_repo import UserRepository
from app.repositories.transaction_repo import TransactionRepository
from app.repositories.alert_repo import FraudAlertRepository
from app.core.security import hash_password


@pytest.mark.unit
class TestRepositoriesUnit:
    def test_user_repository_crud(self, db_session):
        repo = UserRepository(db_session)
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=f"repo_tester_{uuid.uuid4().hex[:6]}@detexa.io",
            hashed_password=hash_password("Password@123"),
            name="Repo Tester",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        repo.create(user, flush=True)

        fetched = repo.get(user_id)
        assert fetched is not None
        assert fetched.id == user_id

        fetched_by_email = repo.get_by_email(user.email)
        assert fetched_by_email is not None
        assert fetched_by_email.id == user_id

    def test_transaction_repository_create_and_list(self, db_session, test_user):
        repo = TransactionRepository(db_session)
        tx_id = uuid.uuid4()
        txn = Transaction(
            id=tx_id,
            transaction_ref=f"TXN-REPO-{uuid.uuid4().hex[:6]}",
            user_id=test_user.id,
            amount=150.0,
            currency="USD",
            merchant="Repo Mart",
            category="Retail",
            country="US",
            risk_level=RiskLevel.LOW,
            fraud_score=0.05,
            is_fraud=False,
            timestamp=datetime.now(timezone.utc),
        )
        repo.create(txn, flush=True)

        fetched = repo.get(tx_id)
        assert fetched is not None
        assert fetched.amount == 150.0
        assert fetched.merchant == "Repo Mart"

    def test_alert_repository_update_status(self, db_session, test_user):
        repo = FraudAlertRepository(db_session)
        alert_id = uuid.uuid4()
        alert = FraudAlert(
            id=alert_id,
            user_id=test_user.id,
            alert_type="RULE_MATCH",
            risk_level=RiskLevel.HIGH.value,
            score=0.88,
            description="Velocity Burst Detected",
            status=AlertStatus.OPEN.value,
            created_at=datetime.now(timezone.utc),
        )
        repo.create(alert, flush=True)

        fetched = repo.get(alert_id)
        assert fetched is not None
        assert fetched.status == AlertStatus.OPEN.value

        updated = repo.update(alert, {"status": AlertStatus.RESOLVED.value}, flush=True)
        assert updated is not None
        assert updated.status == AlertStatus.RESOLVED.value
