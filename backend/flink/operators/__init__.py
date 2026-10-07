"""
flink/operators/__init__.py
─────────────────────────────────────────────────────────────────────────────
Export Flink streaming operators for feature enrichment, ML scoring, decisioning,
and sinking to PostgreSQL and Kafka.
"""

from flink.operators.decision_operator import DecisionOperator
from flink.operators.feature_enrichment_operator import FeatureEnrichmentOperator
from flink.operators.fraud_scoring_operator import FraudScoringOperator
from flink.operators.kafka_sink import KafkaSinkOperator
from flink.operators.postgres_sink import PostgreSQLSinkOperator

__all__ = [
    "DecisionOperator",
    "FeatureEnrichmentOperator",
    "FraudScoringOperator",
    "KafkaSinkOperator",
    "PostgreSQLSinkOperator",
]
