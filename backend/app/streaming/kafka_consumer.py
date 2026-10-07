"""
app/streaming/kafka_consumer.py
─────────────────────────────────────────────────────────────────────────────
Kafka Event Consumer with manual offset control, at-least-once delivery,
and dead-letter queue routing.
"""

import json
import threading
import time
from typing import Callable, Dict, List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.streaming.event_schemas import DeadLetterEvent, EventHeader, EventType, TransactionIngestionEvent
from app.streaming.kafka_producer import KafkaEventProducer


class KafkaEventConsumer:
    """
    Consumer group coordinator for reading streaming transactions from Kafka.
    """

    def __init__(
        self,
        topic: Optional[str] = None,
        group_id: Optional[str] = None,
        on_event_callback: Optional[Callable[[TransactionIngestionEvent], None]] = None,
    ):
        self.topic = topic or settings.kafka_transactions_topic
        self.group_id = group_id or settings.kafka_consumer_group
        self.callback = on_event_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._consumer = None
        self._producer = KafkaEventProducer.get_instance()

    def start(self):
        """Start consumer background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._consume_loop, daemon=True)
        self._thread.start()
        logger.info(f"Kafka consumer started for topic '{self.topic}' [Group: {self.group_id}]")

    def stop(self):
        """Signal consumer thread to gracefully terminate."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info(f"Kafka consumer stopped for topic '{self.topic}'")

    def _consume_loop(self):
        if not settings.kafka_enabled:
            # Poll in-memory buffer in development mode
            while self._running:
                events = self._producer.get_in_memory_events(self.topic)
                # In mock mode, idle sleep to prevent CPU spin
                time.sleep(1.0)
            return

        try:
            try:
                from confluent_kafka import Consumer, KafkaError
                conf = {
                    "bootstrap.servers": settings.kafka_bootstrap_servers,
                    "group.id": self.group_id,
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                }
                if settings.kafka_security_protocol.upper() == "SASL_SSL":
                    conf.update({
                        "security.protocol": "SASL_SSL",
                        "sasl.mechanism": settings.kafka_sasl_mechanism or "PLAIN",
                        "sasl.username": settings.kafka_sasl_username or "",
                        "sasl.password": settings.kafka_sasl_password or "",
                    })
                self._consumer = Consumer(conf)
                self._consumer.subscribe([self.topic])

                while self._running:
                    msg = self._consumer.poll(timeout=1.0)
                    if msg is None:
                        continue
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        else:
                            logger.error(f"Kafka consumer error: {msg.error()}")
                            break

                    raw_val = msg.value().decode("utf-8")
                    try:
                        data = json.loads(raw_val)
                        event = TransactionIngestionEvent(**data)
                        if self.callback:
                            self.callback(event)
                        self._consumer.commit(msg, asynchronous=False)
                    except Exception as exc:
                        logger.error(f"Error processing Kafka message offset {msg.offset()}: {exc}")
                        dlq_event = DeadLetterEvent(
                            header=EventHeader(event_type=EventType.DEAD_LETTER),
                            failed_topic=self.topic,
                            raw_payload=raw_val,
                            error_message=str(exc),
                        )
                        self._producer.send_dlq_event(dlq_event)
                        self._consumer.commit(msg, asynchronous=False)
            except ImportError:
                from kafka import KafkaConsumer as StandardKafkaConsumer
                self._consumer = StandardKafkaConsumer(
                    self.topic,
                    bootstrap_servers=settings.kafka_bootstrap_servers.split(","),
                    group_id=self.group_id,
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,
                    api_version=(3, 7, 0),
                    consumer_timeout_ms=1000,
                )
                logger.info(f"Standard Kafka-Python consumer connected to topic '{self.topic}' targeting {settings.kafka_bootstrap_servers}")

                while self._running:
                    for msg in self._consumer:
                        if not self._running:
                            break
                        raw_val = msg.value.decode("utf-8") if isinstance(msg.value, bytes) else msg.value
                        try:
                            data = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                            event = TransactionIngestionEvent(**data)
                            if self.callback:
                                self.callback(event)
                            self._consumer.commit()
                        except Exception as exc:
                            logger.error(f"Error processing Kafka message offset {msg.offset}: {exc}")
                            dlq_event = DeadLetterEvent(
                                header=EventHeader(event_type=EventType.DEAD_LETTER),
                                failed_topic=self.topic,
                                raw_payload=str(raw_val),
                                error_message=str(exc),
                            )
                            self._producer.send_dlq_event(dlq_event)
                            self._consumer.commit()

        except Exception as exc:
            logger.warning(f"Kafka consumer connection error: {exc}. Retrying in 10s...")
            time.sleep(10.0)
        finally:
            if self._consumer:
                try:
                    self._consumer.close()
                except Exception:
                    pass
