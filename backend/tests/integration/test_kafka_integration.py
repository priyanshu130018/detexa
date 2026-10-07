"""
backend/tests/integration/test_kafka_integration.py
─────────────────────────────────────────────────────────────────────────────
Integration tests connecting directly to the real Apache Kafka broker.
"""

import pytest
import json
import uuid
import time
from kafka import KafkaProducer, KafkaConsumer
from app.core.config import settings


@pytest.mark.integration
class TestKafkaIntegration:
    @classmethod
    def setup_class(cls):
        cls.bootstrap = settings.kafka_bootstrap_servers
        if not cls.bootstrap or cls.bootstrap == "localhost:9092":
            # Check fallback in container
            cls.bootstrap = "kafka:9092"

    def test_kafka_produce_and_consume_event(self):
        topic = "detexa.transactions.raw"
        event_id = f"test-evt-{uuid.uuid4().hex[:8]}"
        payload = {
            "event_id": event_id,
            "amount": 299.99,
            "currency": "USD",
            "merchant": "Kafka Integration Merchant",
        }

        # 1. Produce
        producer = KafkaProducer(
            bootstrap_servers=self.bootstrap,
            api_version=(3, 7, 0),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
        )
        future = producer.send(topic, payload)
        meta = future.get(timeout=10)
        assert meta.topic == topic
        assert meta.offset >= 0
        producer.flush()
        producer.close()

        # 2. Consume with unique consumer group
        group_id = f"test-group-{uuid.uuid4().hex[:8]}"
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap,
            api_version=(3, 7, 0),
            group_id=group_id,
            auto_offset_reset="earliest",
            consumer_timeout_ms=8000,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )

        received = False
        start_time = time.time()
        for msg in consumer:
            if msg.value.get("event_id") == event_id:
                received = True
                assert msg.value["amount"] == 299.99
                break
            if time.time() - start_time > 7.0:
                break
        consumer.close()
        assert received is True
