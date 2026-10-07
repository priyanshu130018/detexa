"""
flink/config.py
─────────────────────────────────────────────────────────────────────────────
PyFlink Streaming Environment Configuration.
Independent from FastAPI; reads settings from environment or defaults.
"""

import os
from dataclasses import dataclass


@dataclass
class FlinkStreamingConfig:
    # ── Kafka Source & Sink ──────────────────────────────────────────────────
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_transactions_raw_topic: str = os.getenv("KAFKA_TRANSACTIONS_TOPIC", "detexa.transactions.raw")
    kafka_transactions_topic: str = os.getenv("KAFKA_TRANSACTIONS_TOPIC", "detexa.transactions.raw")
    kafka_transactions_scored_topic: str = os.getenv("KAFKA_SCORED_TOPIC", "detexa.transactions.scored")
    kafka_alerts_topic: str = os.getenv("KAFKA_ALERTS_TOPIC", "detexa.alerts.high_risk")
    kafka_dlq_topic: str = os.getenv("KAFKA_DLQ_TOPIC", "detexa.dlq")
    kafka_consumer_group: str = os.getenv("FLINK_CONSUMER_GROUP", "detexa-flink-processor-group")
    kafka_enabled: bool = os.getenv("KAFKA_ENABLED", "false").lower() in ("true", "1", "yes")

    # ── PostgreSQL Sink ──────────────────────────────────────────────────────
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://detexa_user:detexa_pass@localhost:5432/detexa_db"
    )

    # ── ML Model Configuration ───────────────────────────────────────────────
    model_path: str = os.getenv("MODEL_PATH", "app/ml/saved")
    credit_model_filename: str = os.getenv("CREDIT_MODEL_FILENAME", "credit_fraud_pipeline.pkl")
    fraud_threshold: float = float(os.getenv("FRAUD_THRESHOLD", "0.50"))
    high_risk_threshold: float = float(os.getenv("HIGH_RISK_THRESHOLD", "0.75"))

    # ── Flink Runtime & Checkpoints ──────────────────────────────────────────
    parallelism: int = int(os.getenv("FLINK_PARALLELISM", "4"))
    checkpoint_interval_ms: int = int(os.getenv("FLINK_CHECKPOINT_INTERVAL_MS", "5000"))
    min_pause_between_checkpoints_ms: int = int(os.getenv("FLINK_MIN_PAUSE_CHECKPOINTS_MS", "500"))
    checkpoint_timeout_ms: int = int(os.getenv("FLINK_CHECKPOINT_TIMEOUT_MS", "60000"))
    watermark_max_out_of_orderness_sec: int = int(os.getenv("FLINK_WATERMARK_LATENCY_SEC", "2"))
    state_retention_hours: int = int(os.getenv("FLINK_STATE_RETENTION_HOURS", "24"))


flink_config = FlinkStreamingConfig()
