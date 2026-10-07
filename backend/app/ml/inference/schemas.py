"""
app/ml/inference/schemas.py
─────────────────────────────────────────────────────────────────────────────
Data models and response structures for low-latency ML inference.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Feature validation outcome."""
    is_valid: bool
    sanitized_features: Dict[str, float]
    warnings: List[str] = field(default_factory=list)


@dataclass
class LowLatencyInferenceResult:
    """
    Standardized inference output container.
    """
    fraud_probability: float
    model_version: str
    risk_level: str
    decision: str
    latency_ms: float
    inference_engine: str  # 'onnx_runtime', 'xgboost_booster_inplace', or 'sklearn_pipeline'
    shap_drivers: Optional[List[Dict[str, Any]]] = None
    validation_warnings: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fraud_probability": round(self.fraud_probability, 5),
            "model_version": self.model_version,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "latency_ms": round(self.latency_ms, 3),
            "inference_engine": self.inference_engine,
            "shap_drivers": self.shap_drivers,
            "validation_warnings": self.validation_warnings,
        }
