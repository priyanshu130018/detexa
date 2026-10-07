"""
backend/tests/integration/test_db_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests for database relations, joins, and ACID commit/rollback.
"""

import pytest
import uuid
from datetime import datetime, timezone
from app.db.models import User, Transaction, FraudAlert, RiskLevel, AlertStatus
from app.core.security import hash_password


@pytest.mark.integration
class TestDatabaseIntegration:
    def test_relational_schema_and_joins(self, db_session):
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email=f"int_usr_{uuid.uuid4().hex[:6]}@detexa.io",
            hashed_password=hash_password("Pass@123"),
            name="Integration User",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)

        tx_id = uuid.uuid4()
        txn = Transaction(
            id=tx_id,
            transaction_ref=f"TXN-INT-{uuid.uuid4().hex[:6]}",
            user_id=user_id,
            amount=850.0,
            currency="USD",
            merchant="Luxury Store",
            category="Luxury",
            country="US",
            risk_level=RiskLevel.HIGH,
            fraud_score=0.78,
            is_fraud=False,
            timestamp=datetime.now(timezone.utc),
        )
        db_session.add(txn)

        alert_id = uuid.uuid4()
        alert = FraudAlert(
            id=alert_id,
            transaction_id=tx_id,
            user_id=user_id,
            alert_type="credit_fraud",
            risk_level=RiskLevel.HIGH.value,
            score=0.78,
            status=AlertStatus.OPEN.value,
            description="High value purchase",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(alert)
        db_session.commit()

        # Query and assert join
        joined_alert = db_session.query(FraudAlert).filter(FraudAlert.id == alert_id).first()
        assert joined_alert is not None
        assert joined_alert.transaction is not None
        assert float(joined_alert.transaction.amount) == 850.0
        assert joined_alert.user.id == user_id

    def test_acid_rollback_isolation(self, db_session):
        test_id = uuid.uuid4()
        user = User(
            id=test_id,
            email="rollback_user@detexa.io",
            hashed_password=hash_password("Pass@123"),
            name="Rollback User",
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.flush()

        # Rollback
        db_session.rollback()

        queried = db_session.query(User).filter(User.id == test_id).first()
        assert queried is None
