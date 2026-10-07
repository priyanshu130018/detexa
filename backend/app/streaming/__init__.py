"""
app/streaming/__init__.py
─────────────────────────────────────────────────────────────────────────────
Real-time streaming pipeline exports (Kafka, Flink, Decision Engine).
"""

from app.streaming.event_schemas import (
    AggregatedFeatures,
    DeadLetterEvent,
    EventHeader,
    EventType,
    FraudAlertEvent,
    ScoredTransactionEvent,
    TransactionIngestionEvent,
    TransactionPayload,
)
from app.streaming.kafka_producer import KafkaEventProducer
from app.streaming.kafka_consumer import KafkaEventConsumer
from app.streaming.decision_engine import RealTimeDecisionEngine
from app.streaming.flink_processor import FlinkRealTimeStreamProcessor

__all__ = [
    "AggregatedFeatures",
    "DeadLetterEvent",
    "EventHeader",
    "EventType",
    "FraudAlertEvent",
    "ScoredTransactionEvent",
    "TransactionIngestionEvent",
    "TransactionPayload",
    "KafkaEventProducer",
    "KafkaEventConsumer",
    "RealTimeDecisionEngine",
    "FlinkRealTimeStreamProcessor",
]
