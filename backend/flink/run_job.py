"""
flink/run_job.py
─────────────────────────────────────────────────────────────────────────────
Standalone CLI Runner for the Detexa Flink Streaming Layer.

Executes continuous real-time stream processing on incoming transaction events:
- Subscribes to `detexa.transactions.raw` Kafka topic.
- Evaluates sliding velocity, monetary, and behavioral windows per user.
- Performs XGBoost real-time fraud scoring.
- Executes multi-tier decision logic (ALLOW, REVIEW, BLOCK).
- Idempotently writes to PostgreSQL and emits scored events to Kafka.
- Provides graceful shutdown and health reporting.

Usage:
  python -m flink.run_job
  python backend/flink/run_job.py
"""

import logging
import os
import signal
import sys
import time
from typing import Any, Dict

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from flink.config import flink_config
from flink.job import TransactionFraudStreamingJob
from app.streaming.kafka_consumer import KafkaEventConsumer

logger = logging.getLogger("detexa.flink.runner")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class FlinkStreamRunner:
    """
    Continuous streaming worker runner that connects Kafka consumer to the Flink Job pipeline.
    """

    def __init__(self):
        self.job = TransactionFraudStreamingJob()
        self.consumer = KafkaEventConsumer(
            topic=flink_config.kafka_transactions_topic,
            group_id=flink_config.kafka_consumer_group,
            on_event_callback=self._handle_event,
        )
        self.is_running = False
        self.total_processed = 0
        self.total_frauds_detected = 0
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info(f"Received shutdown signal ({signum}). Gracefully stopping Flink streaming pipeline...")
        self.stop()

    def stop(self):
        self.is_running = False
        self.consumer.stop()
        logger.info(
            f"Flink stream worker stopped. Summary: {self.total_processed} processed, "
            f"{self.total_frauds_detected} high-risk flags."
        )

    def _handle_event(self, event_data: Any):
        try:
            if hasattr(event_data, "model_dump"):
                raw_event_dict = event_data.model_dump()
            elif hasattr(event_data, "dict"):
                raw_event_dict = event_data.dict()
            elif isinstance(event_data, dict):
                raw_event_dict = event_data
            else:
                raw_event_dict = dict(event_data)

            res = self.job.process_single_event(raw_event_dict)
            self.total_processed += 1
            if res.get("decision") in ("BLOCK", "REVIEW"):
                self.total_frauds_detected += 1
                logger.warning(
                    f"⚠️ [FLINK ALERT] Txn: {res.get('transaction_ref')} | Decision: {res.get('decision')} | "
                    f"Score: {res.get('fraud_score', 0.0):.4f} | Reasons: {res.get('reason_codes')} | "
                    f"Latency: {res.get('latency_ms', 0.0)}ms"
                )
            else:
                logger.info(
                    f"✅ [FLINK OK] Txn: {res.get('transaction_ref')} | User: {res.get('user_id')} | "
                    f"Amount: ${res.get('amount', 0.0):.2f} | Score: {res.get('fraud_score', 0.0):.4f} | "
                    f"Velocity(1m): {res.get('window_metrics', {}).get('velocity_1m', 0)} | "
                    f"Latency: {res.get('latency_ms', 0.0)}ms"
                )
        except Exception as exc:
            logger.error(f"Error processing streaming event: {exc}", exc_info=True)

    def start(self):
        self.is_running = True
        logger.info("=" * 70)
        logger.info("🚀 Starting Detexa Flink Real-Time Stream Processing Worker")
        logger.info(f"   Kafka Source Topic : {flink_config.kafka_transactions_topic}")
        logger.info(f"   Consumer Group     : {flink_config.kafka_consumer_group}")
        logger.info(f"   PostgreSQL Target  : {flink_config.database_url.split('@')[-1] if '@' in flink_config.database_url else flink_config.database_url}")
        logger.info(f"   Kafka Scored Topic : {flink_config.kafka_transactions_topic}.scored")
        logger.info(f"   Parallelism        : {flink_config.parallelism}")
        logger.info(f"   Fraud Threshold    : {flink_config.fraud_threshold}")
        logger.info("=" * 70)

        # In case PyFlink engine is deployed:
        pyflink_env = self.job.build_pyflink_environment()
        if pyflink_env is not None:
            logger.info("PyFlink execution environment active.")

        # Start continuous Kafka event stream consumption
        try:
            self.consumer.start()
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.stop()


def main():
    runner = FlinkStreamRunner()
    runner.start()


if __name__ == "__main__":
    main()
