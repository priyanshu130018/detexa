"""
app/api/v1/endpoints/streaming.py
─────────────────────────────────────────────────────────────────────────────
Real-time Transaction Event Streaming REST API endpoints (Kafka -> Flink -> Postgres).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import User
from app.streaming.event_schemas import (
    EventHeader,
    EventType,
    ScoredTransactionEvent,
    TransactionIngestionEvent,
    TransactionPayload,
)
from app.streaming.flink_processor import FlinkRealTimeStreamProcessor
from app.streaming.kafka_producer import KafkaEventProducer

router = APIRouter(prefix="/streaming", tags=["Real-Time Streaming Pipeline"])


class IngestionReceipt(BaseModel):
    event_id: str
    idempotency_key: str
    transaction_ref: str
    status: str = "QUEUED"
    topic: str
    timestamp: str


class StreamPipelineMetrics(BaseModel):
    kafka_enabled: bool
    kafka_bootstrap_servers: str
    transactions_topic: str
    alerts_topic: str
    in_memory_queue_depth: Dict[str, int]
    timestamp: str


@router.post(
    "/transactions",
    response_model=IngestionReceipt,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest Transaction to Kafka Stream (Async)",
    description="Publishes an idempotent transaction event to the 'detexa.transactions.raw' Kafka topic for asynchronous Flink processing.",
)
def ingest_transaction_stream(
    payload: TransactionPayload,
    idempotency_key: Optional[str] = Query(
        None, description="Optional client idempotency key to prevent duplicate message ingestion"
    ),
    current_user: User = Depends(get_current_user),
) -> IngestionReceipt:
    producer = KafkaEventProducer.get_instance()

    effective_idempotency_key = idempotency_key or str(uuid.uuid4())
    if not payload.user_id:
        payload.user_id = str(current_user.id)

    event_header = EventHeader(
        event_id=str(uuid.uuid4()),
        idempotency_key=effective_idempotency_key,
        event_type=EventType.TRANSACTION_INGESTED,
        source="detexa-transaction-api",
        partition_key=payload.user_id or payload.transaction_ref,
    )

    ingestion_event = TransactionIngestionEvent(header=event_header, payload=payload)
    producer.send_transaction_event(ingestion_event)

    return IngestionReceipt(
        event_id=event_header.event_id,
        idempotency_key=effective_idempotency_key,
        transaction_ref=payload.transaction_ref,
        status="QUEUED",
        topic=settings.kafka_transactions_topic,
        timestamp=event_header.timestamp,
    )


@router.post(
    "/transactions/process-sync",
    response_model=ScoredTransactionEvent,
    status_code=status.HTTP_200_OK,
    summary="Process Transaction via Real-Time Pipeline (Sync Roundtrip)",
    description="Executes the full pipeline in real-time: Ingestion -> Flink Sliding Windows -> XGBoost Scoring -> Decision Engine -> PostgreSQL Persistence -> Kafka Egress.",
)
def process_transaction_sync(
    payload: TransactionPayload,
    idempotency_key: Optional[str] = Query(
        None, description="Idempotency token ensuring exactly-once execution"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScoredTransactionEvent:
    if not payload.user_id:
        payload.user_id = str(current_user.id)

    effective_idempotency_key = idempotency_key or str(uuid.uuid4())

    event_header = EventHeader(
        event_id=str(uuid.uuid4()),
        idempotency_key=effective_idempotency_key,
        event_type=EventType.TRANSACTION_INGESTED,
        source="detexa-transaction-api",
        partition_key=payload.user_id or payload.transaction_ref,
    )

    ingestion_event = TransactionIngestionEvent(header=event_header, payload=payload)

    # 1. Publish to raw Kafka topic
    producer = KafkaEventProducer.get_instance()
    producer.send_transaction_event(ingestion_event)

    # 2. Process through Flink engine & PostgreSQL sink
    processor = FlinkRealTimeStreamProcessor.get_instance()
    return processor.process_transaction_event(ingestion_event, db=db)


@router.get(
    "/metrics",
    response_model=StreamPipelineMetrics,
    summary="Get Streaming Pipeline Diagnostics",
    description="Retrieve real-time telemetry on Kafka connection state and stream queue depths.",
)
def get_streaming_metrics(
    _: User = Depends(get_current_user),
) -> StreamPipelineMetrics:
    producer = KafkaEventProducer.get_instance()
    raw_depth = len(producer.get_in_memory_events(settings.kafka_transactions_topic))
    alert_depth = len(producer.get_in_memory_events(settings.kafka_alerts_topic))
    scored_depth = len(producer.get_in_memory_events("detexa.transactions.scored"))

    return StreamPipelineMetrics(
        kafka_enabled=settings.kafka_enabled,
        kafka_bootstrap_servers=settings.kafka_bootstrap_servers,
        transactions_topic=settings.kafka_transactions_topic,
        alerts_topic=settings.kafka_alerts_topic,
        in_memory_queue_depth={
            settings.kafka_transactions_topic: raw_depth,
            settings.kafka_alerts_topic: alert_depth,
            "detexa.transactions.scored": scored_depth,
        },
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
