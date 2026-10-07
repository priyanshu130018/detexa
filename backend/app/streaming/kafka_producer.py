"""
app/streaming/kafka_producer.py
─────────────────────────────────────────────────────────────────────────────
High-throughput, idempotent Kafka event producer module.
Uses Kafka strictly for event streaming (no Redis message broker).
Includes in-memory simulation fallback for local development when Kafka is offline.
"""

from collections import deque
import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.streaming.event_schemas import (
    DeadLetterEvent,
    EventType,
    FraudAlertEvent,
    ScoredTransactionEvent,
    TransactionIngestionEvent,
)


class KafkaEventProducer:
    """
    Thread-safe Kafka Producer supporting deterministic key partitioning,
    idempotent publishing, delivery verification, and in-memory buffer fallback.
    """

    _instance: Optional["KafkaEventProducer"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._producer = None
        self._enabled = settings.kafka_enabled
        self._bootstrap_servers = settings.kafka_bootstrap_servers
        self._in_memory_buffers: Dict[str, deque] = {
            settings.kafka_transactions_topic: deque(maxlen=5000),
            settings.kafka_alerts_topic: deque(maxlen=5000),
            "detexa.transactions.scored": deque(maxlen=5000),
            "detexa.dlq": deque(maxlen=1000),
        }
        self._init_producer()

    @classmethod
    def get_instance(cls) -> "KafkaEventProducer":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _init_producer(self):
        if not self._enabled:
            logger.info("Kafka producer operating in in-memory event stream mode (kafka_enabled=False).")
            return

        try:
            # Try importing confluent_kafka or kafka-python
            try:
                from confluent_kafka import Producer
                conf = {
                    "bootstrap.servers": self._bootstrap_servers,
                    "client.id": settings.kafka_client_id,
                    "enable.idempotence": True,
                    "acks": "all",
                    "retries": 5,
                    "max.in.flight.requests.per.connection": 1,
                    "compression.type": "snappy",
                }
                if settings.kafka_security_protocol.upper() == "SASL_SSL":
                    conf.update({
                        "security.protocol": "SASL_SSL",
                        "sasl.mechanism": settings.kafka_sasl_mechanism or "PLAIN",
                        "sasl.username": settings.kafka_sasl_username or "",
                        "sasl.password": settings.kafka_sasl_password or "",
                    })
                self._producer = Producer(conf)
                logger.info(f"Confluent-Kafka producer initialized targeting {self._bootstrap_servers}")
            except ImportError:
                from kafka import KafkaProducer as StandardKafkaProducer
                self._producer = StandardKafkaProducer(
                    bootstrap_servers=self._bootstrap_servers.split(","),
                    client_id=settings.kafka_client_id,
                    api_version=(3, 7, 0),
                    acks="all",
                    retries=5,
                    max_in_flight_requests_per_connection=1,
                    value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
                    key_serializer=lambda k: k.encode("utf-8") if k else None,
                )
                logger.info(f"Standard Kafka-Python producer initialized targeting {self._bootstrap_servers}")
        except Exception as exc:
            logger.warning(
                f"Could not connect to Kafka brokers at {self._bootstrap_servers} ({exc}). "
                "Failing over to in-memory streaming buffer."
            )
            self._producer = None

    def send_transaction_event(
        self,
        event: TransactionIngestionEvent,
        topic: Optional[str] = None,
    ) -> bool:
        """Publish raw transaction ingestion event to Kafka."""
        target_topic = topic or settings.kafka_transactions_topic
        partition_key = event.header.partition_key or event.payload.user_id or event.payload.transaction_ref
        payload_dict = event.model_dump()
        return self._send(target_topic, partition_key, payload_dict)

    def send_scored_event(
        self,
        event: ScoredTransactionEvent,
        topic: str = "detexa.transactions.scored",
    ) -> bool:
        """Publish evaluated score & decision event to Kafka."""
        partition_key = event.header.partition_key or event.payload.user_id or event.payload.transaction_ref
        payload_dict = event.model_dump()
        return self._send(topic, partition_key, payload_dict)

    def send_alert_event(
        self,
        event: FraudAlertEvent,
        topic: Optional[str] = None,
    ) -> bool:
        """Publish high-risk security alert to Kafka."""
        target_topic = topic or settings.kafka_alerts_topic
        partition_key = event.user_id or event.transaction_ref
        payload_dict = event.model_dump()
        return self._send(target_topic, partition_key, payload_dict)

    def send_dlq_event(
        self,
        event: DeadLetterEvent,
        topic: str = "detexa.dlq",
    ) -> bool:
        """Publish poisoned message to Dead Letter Queue topic."""
        partition_key = event.header.event_id
        payload_dict = event.model_dump()
        return self._send(topic, partition_key, payload_dict)

    def _send(self, topic: str, key: Optional[str], value: Dict[str, Any]) -> bool:
        if not self._enabled:
            # Explicit local development/offline mode: buffer in in-memory event stream
            if topic in self._in_memory_buffers:
                self._in_memory_buffers[topic].append({"key": key, "value": value, "published_at": time.time()})
            logger.debug(f"[Stream Mock] Event buffered offline to topic '{topic}' with key '{key}'")
            return True

        if self._producer is None:
            logger.error(
                f"Kafka message drop: Broker connection unavailable at {self._bootstrap_servers} for topic '{topic}'."
            )
            return False

        try:
            # Confluent-kafka producer
            if hasattr(self._producer, "produce"):
                self._producer.produce(
                    topic=topic,
                    key=str(key) if key else None,
                    value=json.dumps(value, default=str).encode("utf-8"),
                    callback=self._delivery_report,
                )
                self._producer.poll(0)
            else:
                # Kafka-python producer
                future = self._producer.send(topic=topic, key=key, value=value)
                if hasattr(future, "add_errback"):
                    future.add_errback(lambda exc: logger.error(f"Kafka async send error: {exc}"))
            return True
        except Exception as exc:
            logger.error(f"Kafka send failure on topic '{topic}': {exc}")
            return False

    def _delivery_report(self, err, msg):
        if err is not None:
            logger.error(f"Kafka message delivery failed: {err}")
        else:
            logger.debug(f"Kafka message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

    def flush(self, timeout: float = 2.0):
        if self._producer and hasattr(self._producer, "flush"):
            self._producer.flush(timeout)

    def get_in_memory_events(self, topic: str) -> List[Dict[str, Any]]:
        """Retrieve historical stream events from in-memory stream buffer for debugging/testing."""
        if topic in self._in_memory_buffers:
            return list(self._in_memory_buffers[topic])
        return []
