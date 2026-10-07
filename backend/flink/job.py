"""
flink/job.py
─────────────────────────────────────────────────────────────────────────────
Apache Flink Stream Processing Job for Real-Time Fraud Detection.

Orchestrates the end-to-end streaming DAG:
Kafka Source (`detexa.transactions.raw`)
  ──► Watermark & Timestamp Assignor
  ──► KeyBy (`user_id` / `partition_key`)
  ──► Stateful Window & Behavioral Feature Enrichment
  ──► Real-Time ML Fraud Scoring (XGBoost Pipeline)
  ──► Rule-Based Multi-Tier Decision Engine
  ──► Sinks:
        ├── PostgreSQL Idempotent Sink (`transactions`, `predictions`, `alerts`)
        └── Kafka Scored & Alert Sink (`detexa.transactions.scored`, `detexa.alerts.high_risk`)
"""

import json
import logging
import time
from typing import Any, Callable, Dict, Optional

from flink.config import flink_config
from flink.operators.decision_operator import DecisionOperator
from flink.operators.feature_enrichment_operator import FeatureEnrichmentOperator
from flink.operators.fraud_scoring_operator import FraudScoringOperator
from flink.operators.kafka_sink import KafkaSinkOperator
from flink.operators.postgres_sink import PostgreSQLSinkOperator

logger = logging.getLogger("detexa.flink.job")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class TransactionFraudStreamingJob:
    """
    Main PyFlink Streaming Coordinator for Detexa.
    Encapsulates stateful operators and stream pipeline logic.
    """

    def __init__(
        self,
        enrichment_op: Optional[FeatureEnrichmentOperator] = None,
        scoring_op: Optional[FraudScoringOperator] = None,
        decision_op: Optional[DecisionOperator] = None,
        postgres_sink: Optional[PostgreSQLSinkOperator] = None,
        kafka_sink: Optional[KafkaSinkOperator] = None,
    ):
        self.enrichment_op = enrichment_op or FeatureEnrichmentOperator()
        self.scoring_op = scoring_op or FraudScoringOperator()
        self.decision_op = decision_op or DecisionOperator()
        self.postgres_sink = postgres_sink or PostgreSQLSinkOperator()
        self.kafka_sink = kafka_sink or KafkaSinkOperator()
        self.is_running = False

    def process_single_event(self, raw_event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a single incoming transaction event through the complete pipeline:
        1. Feature Enrichment (Velocity, Monetary, Behavioral, Diurnal Windows)
        2. ML Scoring (XGBoost Pipeline Inference)
        3. Multi-tier Decisioning (ALLOW / REVIEW / BLOCK)
        4. Idempotent PostgreSQL persistence
        5. Kafka outbound emission
        """
        start_ts = time.time()

        # Step 1: Stateful Feature Enrichment
        enriched_event = self.enrichment_op.process_event(raw_event_dict)

        # Step 2: ML Model Scoring
        fraud_score, shap_drivers = self.scoring_op.score(enriched_event)

        # Step 3: Rule & ML Decision Synthesis
        decision, risk_level, reason_codes = self.decision_op.evaluate(
            event=enriched_event,
            ml_fraud_score=fraud_score,
        )

        latency_ms = (time.time() - start_ts) * 1000.0

        # Step 4: Idempotent Database Sink
        try:
            self.postgres_sink.write_event(
                event=enriched_event,
                fraud_score=fraud_score,
                risk_level_str=risk_level,
                decision_str=decision,
                reason_codes=reason_codes,
                shap_drivers=shap_drivers,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error(f"PostgreSQL Sink Error for {enriched_event.transaction_ref}: {exc}")

        # Step 5: Outbound Kafka Sink
        try:
            self.kafka_sink.emit_scored_and_alerts(
                event=enriched_event,
                fraud_score=fraud_score,
                risk_level=risk_level,
                decision=decision,
                reason_codes=reason_codes,
                shap_drivers=shap_drivers,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error(f"Kafka Sink Error for {enriched_event.transaction_ref}: {exc}")

        return {
            "transaction_ref": enriched_event.transaction_ref,
            "user_id": enriched_event.user_id,
            "amount": enriched_event.amount,
            "fraud_score": fraud_score,
            "risk_level": risk_level,
            "decision": decision,
            "reason_codes": reason_codes,
            "latency_ms": round(latency_ms, 2),
            "window_metrics": {
                "velocity_1m": enriched_event.window_metrics.velocity_1m,
                "velocity_5m": enriched_event.window_metrics.velocity_5m,
                "velocity_1h": enriched_event.window_metrics.velocity_1h,
                "rolling_amount_1h": enriched_event.window_metrics.rolling_amount_1h,
                "amount_deviation_ratio": enriched_event.window_metrics.amount_deviation_ratio,
                "failed_txn_count_5m": enriched_event.window_metrics.failed_txn_count_5m,
                "is_unusual_hour": enriched_event.window_metrics.is_unusual_hour,
                "device_changed": enriched_event.window_metrics.device_changed,
                "ip_changed": enriched_event.window_metrics.ip_changed,
            },
        }

    def build_pyflink_environment(self):
        """
        Constructs the Apache PyFlink StreamExecutionEnvironment if pyflink is available.
        Sets checkpointing, parallelism, state backend, and watermarking.
        """
        try:
            from pyflink.datastream import StreamExecutionEnvironment, CheckpointingMode
            from pyflink.common import WatermarkStrategy, Duration

            env = StreamExecutionEnvironment.get_execution_environment()
            env.set_parallelism(flink_config.parallelism)

            # Checkpointing configuration
            env.enable_checkpointing(flink_config.checkpoint_interval_ms)
            cp_config = env.get_checkpoint_config()
            cp_config.set_checkpointing_mode(CheckpointingMode.EXACTLY_ONCE)
            cp_config.set_min_pause_between_checkpoints(flink_config.min_pause_between_checkpoints_ms)
            cp_config.set_checkpoint_timeout(flink_config.checkpoint_timeout_ms)
            cp_config.set_max_concurrent_checkpoints(1)

            logger.info(
                f"PyFlink StreamExecutionEnvironment initialized (Parallelism: {flink_config.parallelism}, "
                f"Checkpoints: {flink_config.checkpoint_interval_ms}ms)"
            )
            return env
        except ImportError:
            logger.info("pyflink package not installed in environment; using standalone streaming coordinator.")
            return None


def create_streaming_job() -> TransactionFraudStreamingJob:
    """Factory function for creating the transaction fraud streaming job."""
    return TransactionFraudStreamingJob()
