"""
flink/operators/postgres_sink.py
─────────────────────────────────────────────────────────────────────────────
Idempotent PostgreSQL Sink Operator for PyFlink stream pipelines.
Ensures exactly-once delivery semantics via deterministic idempotency keys and
atomic multi-table SQL transaction blocks.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from flink.config import flink_config
from flink.models.state_schemas import FlinkEnrichedEvent
from app.db.models import (
    AlertStatus,
    AuditLog,
    DecisionType,
    Device,
    FraudAlert,
    FraudPrediction,
    IPAddress,
    Merchant,
    RiskLevel,
    Transaction,
)


class PostgreSQLSinkOperator:
    """
    Thread-safe PostgreSQL sink operator with connection pooling and idempotent inserts.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or flink_config.database_url
        self.is_sqlite = self.db_url.startswith("sqlite")
        engine_kwargs = {}
        if self.is_sqlite:
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs.update({
                "pool_size": 5,
                "max_overflow": 10,
                "pool_pre_ping": True,
            })
        self.engine = create_engine(self.db_url, **engine_kwargs)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def write_event(
        self,
        event: FlinkEnrichedEvent,
        fraud_score: float,
        risk_level_str: str,
        decision_str: str,
        reason_codes: List[str],
        shap_drivers: Optional[List[Dict[str, Any]]],
        latency_ms: float,
    ):
        """
        Idempotent write into normalized PostgreSQL tables.
        """
        session: Session = self.SessionLocal()
        try:
            # 1. Idempotency Check: if transaction_ref exists, skip duplicate insert
            existing = (
                session.query(Transaction)
                .filter(Transaction.transaction_ref == event.transaction_ref)
                .first()
            )
            if existing:
                return

            user_id_val: Optional[uuid.UUID] = None
            if event.user_id:
                try:
                    user_id_val = uuid.UUID(str(event.user_id))
                except ValueError:
                    pass

            # 2. Resolve Merchant
            merchant = session.query(Merchant).filter(Merchant.name == event.merchant).first()
            if not merchant:
                merchant = Merchant(
                    id=uuid.uuid4(),
                    name=event.merchant,
                    category=event.category,
                    risk_score=0.0,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(merchant)
                session.flush()

            # 3. Resolve Device
            device = None
            if event.device_fingerprint:
                device = session.query(Device).filter(Device.device_fingerprint == event.device_fingerprint).first()
                if not device:
                    device = Device(
                        id=uuid.uuid4(),
                        user_id=user_id_val,
                        device_fingerprint=event.device_fingerprint,
                        is_trusted=not event.window_metrics.device_changed,
                        first_seen_at=datetime.now(timezone.utc),
                        last_seen_at=datetime.now(timezone.utc),
                    )
                    session.add(device)
                    session.flush()

            # 4. Resolve IP
            ip_obj = None
            if event.ip_address and event.ip_address not in ("0.0.0.0", ""):
                ip_obj = session.query(IPAddress).filter(IPAddress.ip_address == event.ip_address).first()
                if not ip_obj:
                    ip_obj = IPAddress(
                        id=uuid.uuid4(),
                        ip_address=event.ip_address,
                        geo_country=event.country,
                        reputation_score=0.0,
                        last_checked_at=datetime.now(timezone.utc),
                    )
                    session.add(ip_obj)
                    session.flush()

            risk_level_enum = RiskLevel(risk_level_str)
            decision_enum = DecisionType(decision_str)
            is_fraud = (decision_enum == DecisionType.BLOCK or fraud_score >= flink_config.fraud_threshold)

            # 5. Insert Transaction
            txn = Transaction(
                id=uuid.uuid4(),
                user_id=user_id_val,
                merchant_id=merchant.id,
                device_id=device.id if device else None,
                ip_id=ip_obj.id if ip_obj else None,
                transaction_ref=event.transaction_ref,
                amount=event.amount,
                transaction_amount=event.amount,
                currency=event.currency,
                merchant=merchant.name,
                category=merchant.category,
                country=event.country,
                fraud_score=fraud_score,
                risk_level=risk_level_enum,
                is_fraud=is_fraud,
                label=int(decision_enum == DecisionType.BLOCK),
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(1, 29):
                k = f"v{i}"
                setattr(txn, k, event.pca_features.get(k, 0.0))

            session.add(txn)
            session.flush()

            # 6. Insert FraudPrediction Log
            pred = FraudPrediction(
                id=uuid.uuid4(),
                transaction_id=txn.id,
                endpoint="/flink/stream-job",
                input_hash=event.idempotency_key,
                fraud_score=fraud_score,
                anomaly_score=None,
                risk_level=risk_level_enum,
                is_fraud=is_fraud,
                decision=decision_enum,
                shap_values=shap_drivers,
                latency_ms=round(latency_ms, 2),
                model_version="2.0.0",
                created_at=datetime.now(timezone.utc),
            )
            session.add(pred)
            session.flush()

            # 7. Insert FraudAlert if elevated risk
            if decision_enum != DecisionType.ALLOW or fraud_score >= flink_config.fraud_threshold:
                alert = FraudAlert(
                    id=uuid.uuid4(),
                    user_id=txn.user_id,
                    transaction_id=txn.id,
                    prediction_id=pred.id,
                    alert_type="flink_streaming_fraud",
                    risk_level=risk_level_enum,
                    score=fraud_score,
                    description=(
                        f"Flink stream alert on ${event.amount:.2f} at {merchant.name} "
                        f"[Decision: {decision_str}, Triggers: {', '.join(reason_codes)}]"
                    ),
                    status=AlertStatus.OPEN,
                    shap_values=shap_drivers,
                    metadata_={
                        "window_metrics": {
                            "velocity_1m": event.window_metrics.velocity_1m,
                            "velocity_5m": event.window_metrics.velocity_5m,
                            "failed_5m": event.window_metrics.failed_txn_count_5m,
                            "deviation": event.window_metrics.amount_deviation_ratio,
                            "is_unusual_hour": event.window_metrics.is_unusual_hour,
                        },
                        "reason_codes": reason_codes,
                    },
                    created_at=datetime.now(timezone.utc),
                )
                session.add(alert)

            # 8. Insert AuditLog
            audit = AuditLog(
                id=uuid.uuid4(),
                user_id=txn.user_id,
                action="FLINK_STREAM_PROCESSED",
                entity_type="transaction",
                entity_id=str(txn.id),
                ip_address=event.ip_address,
                details={
                    "transaction_ref": event.transaction_ref,
                    "decision": decision_str,
                    "risk_level": risk_level_str,
                    "fraud_score": fraud_score,
                    "reason_codes": reason_codes,
                },
                created_at=datetime.now(timezone.utc),
            )
            session.add(audit)

            session.commit()
        except Exception as exc:
            session.rollback()
            raise exc
        finally:
            session.close()
