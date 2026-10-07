"""
app/features/__init__.py
─────────────────────────────────────────────────────────────────────────────
Unified Fraud Feature Building Layer for Detexa Platform.
"""

from app.features.builder import UnifiedFraudFeatureBuilder
from app.features.models import UnifiedFeatureVector
from app.features.schema import (
    CANONICAL_FEATURE_DEFINITIONS,
    CANONICAL_FEATURE_NAMES,
    FEATURE_DEFAULT_MAP,
    FEATURE_SCHEMA_VERSION,
    FeatureDefinition,
    FeatureGroup,
    TOTAL_FEATURE_COUNT,
)

__all__ = [
    "CANONICAL_FEATURE_DEFINITIONS",
    "CANONICAL_FEATURE_NAMES",
    "FEATURE_DEFAULT_MAP",
    "FEATURE_SCHEMA_VERSION",
    "FeatureDefinition",
    "FeatureGroup",
    "TOTAL_FEATURE_COUNT",
    "UnifiedFeatureVector",
    "UnifiedFraudFeatureBuilder",
]
