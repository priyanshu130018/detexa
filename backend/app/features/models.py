"""
app/features/models.py
─────────────────────────────────────────────────────────────────────────────
Unified feature data structures and extraction containers.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from app.features.schema import (
    CANONICAL_FEATURE_NAMES,
    FEATURE_DEFAULT_MAP,
    FEATURE_SCHEMA_VERSION,
)


@dataclass
class UnifiedFeatureVector:
    """
    Immutable representation of a fully enriched and unified feature vector.
    Enforces strict alignment with the CANONICAL_FEATURE_NAMES order.
    """
    values: Dict[str, float]
    schema_version: str = FEATURE_SCHEMA_VERSION
    user_id: Optional[str] = None
    transaction_ref: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    raw_context: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Guarantee all canonical features are present with default imputations
        for col, default_val in FEATURE_DEFAULT_MAP.items():
            if col not in self.values:
                self.values[col] = default_val

    def get(self, feature_name: str, default: float = 0.0) -> float:
        """Retrieve single feature value."""
        return self.values.get(feature_name.lower(), default)

    def to_dict(self) -> Dict[str, float]:
        """Returns ordered dictionary of canonical features."""
        return {col: float(self.values.get(col, FEATURE_DEFAULT_MAP[col])) for col in CANONICAL_FEATURE_NAMES}

    def to_dataframe(self) -> pd.DataFrame:
        """Returns single-row DataFrame strictly adhering to canonical feature ordering."""
        row_dict = {col: [float(self.values.get(col, FEATURE_DEFAULT_MAP[col]))] for col in CANONICAL_FEATURE_NAMES}
        return pd.DataFrame(row_dict, columns=CANONICAL_FEATURE_NAMES)

    def to_numpy(self) -> np.ndarray:
        """Returns 1D NumPy float32 array aligned with canonical feature schema."""
        return np.array(
            [float(self.values.get(col, FEATURE_DEFAULT_MAP[col])) for col in CANONICAL_FEATURE_NAMES],
            dtype=np.float32,
        )

    def to_inference_dict(self) -> Dict[str, Any]:
        """Returns serialized structure including feature values and contextual metadata."""
        return {
            "schema_version": self.schema_version,
            "user_id": self.user_id,
            "transaction_ref": self.transaction_ref,
            "timestamp": self.timestamp,
            "feature_count": len(CANONICAL_FEATURE_NAMES),
            "features": self.to_dict(),
        }
