"""
flink/operators/kafka_sink.py
─────────────────────────────────────────────────────────────────────────────
Kafka Sink Operator for emitting scored transaction and alert events.
"""

from typing import Any, Dict, List, Optional
import uuid

from flink.config import flink_config
from flink.models.state_schemas import FlinkEnrichedEvent
from app.streaming.event_schemas import (
    AggregatedFeatures,
    EventHeader,
    EventType,
    FraudAlertEvent,
    ScoredTransactionEvent,
    TransactionPayload,
)
from app.streaming.kafka_producer import KafkaEventProducer


class KafkaSinkOperator:
    """
    Egress sink producing scored events and alert messages back to Kafka topics.
    """

    def __init__(self):
        self.producer = KafkaEventProducer.get_instance()

    def emit_scored_and_alerts(
        self,
        event: FlinkEnrichedEvent,
        fraud_score: float,
        risk_level: str,
        decision: str,
        reason_codes: List[str],
        shap_drivers: Optional[List[Dict[str, Any]]],
        latency_ms: float,
    ):
        # 1. Emit Scored Transaction Event
        header = EventHeader(
            event_id=str(uuid.uuid4()),
            idempotency_key=event.idempotency_key,
            event_type=EventType.TRANSACTION_SCORED,
            source="detexa-flink-stream-processor",
            partition_key=event.user_id or event.transaction_ref,
        )

        payload = TransactionPayload(
            transaction_ref=event.transaction_ref,
            amount=event.amount,
            currency=event.currency,
            merchant=event.merchant,
            category=event.category,
            country=event.country,
            user_id=event.user_id,
            device_fingerprint=event.device_fingerprint,
            ip_address=event.ip_address,
            **event.pca_features,
        )

        streaming_features = AggregatedFeatures(
            velocity_1m=event.window_metrics.velocity_1m,
            velocity_5m=event.window_metrics.velocity_5m,
            velocity_1h=event.window_metrics.velocity_1h,
            rolling_amount_1h=event.window_metrics.rolling_amount_1h,
            avg_amount_1h=event.window_metrics.avg_amount_1h,
            amount_deviation_ratio=event.window_metrics.amount_deviation_ratio,
            distinct_merchants_1h=event.window_metrics.distinct_merchants_1h,
            is_foreign_transaction=False,
            is_new_device=event.window_metrics.device_changed,
        )

        scored_event = ScoredTransactionEvent(
            header=header,
            payload=payload,
            streaming_features=streaming_features,
            fraud_score=fraud_score,
            risk_level=risk_level,
            decision=decision,
            reason_codes=reason_codes,
            shap_top_features=shap_drivers,
            latency_ms=round(latency_ms, 2),
            model_version="2.0.0",
        )

        self.producer.send_scored_event(scored_event, topic=flink_config.kafka_transactions_scored_topic)

        # 2. Emit Alert if needed
        if decision != "ALLOW" or fraud_score >= flink_config.fraud_threshold:
            alert_header = EventHeader(
                event_id=str(uuid.uuid4()),
                idempotency_key=event.idempotency_key,
                event_type=EventType.ALERT_GENERATED,
                source="detexa-flink-stream-processor",
                partition_key=event.user_id or event.transaction_ref,
            )
            alert_event = FraudAlertEvent(
                header=alert_header,
                alert_id=str(uuid.uuid4()),
                transaction_id=event.transaction_ref,
                transaction_ref=event.transaction_ref,
                user_id=event.user_id,
                score=fraud_score,
                risk_level=risk_level,
                decision=decision,
                description=(
                    f"Flink Real-Time Alert on ${event.amount:.2f} at {event.merchant} "
                    f"[{decision}, Velocity: {event.window_metrics.velocity_1m}/min, Reason: {', '.join(reason_codes)}]"
                ),
                reason_codes=reason_codes,
                shap_drivers=shap_drivers,
            )
            self.producer.send_alert_event(alert_event, topic=flink_config.kafka_alerts_topic)
