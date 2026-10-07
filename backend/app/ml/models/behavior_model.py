"""
app/ml/models/behavior_model.py
─────────────────────────────────────────────────────────────────────────────
Isolation Forest wrapper for behavioral anomaly detection.
"""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.logging import logger


class BehaviorPipeline:
    """Class wrapper saved inside behavior_pipeline.pkl."""
    def __init__(self, eng, model):
        self.eng = eng
        self.model = model

    def score_samples(self, df_raw):
        return self.model.score_samples(self.eng.transform(df_raw))


class BehaviorAnomalyModel:
    MODEL_VERSION = "2.0.0"
    _instance: Optional["BehaviorAnomalyModel"] = None

    def __init__(self):
        self._pipeline = None
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "BehaviorAnomalyModel":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        possible_paths = [
            Path(settings.model_path) / "behavior_pipeline.pkl",
            Path("app/ml/saved/behavior_pipeline.pkl"),
            Path("ml/models/saved/behavior_pipeline.pkl"),
            Path("backend/app/ml/saved/behavior_pipeline.pkl"),
        ]

        path = next((p for p in possible_paths if p.exists()), None)

        if not path:
            logger.warning(
                f"Behavior model not found in paths: {[str(p) for p in possible_paths]}. "
                "Inference will fall back to simulated scores."
            )
            return

        try:
            import sys
            import app.ml
            import app.ml.models.behavior_model
            import app.ml.pipelines.feature_engineering

            # Alias legacy 'ml' root package to 'app.ml' for deterministic unpickling
            sys.modules.setdefault("ml", app.ml)
            if "app.ml.models" in sys.modules:
                sys.modules.setdefault("ml.models", sys.modules["app.ml.models"])
            sys.modules.setdefault("ml.models.behavior_model", app.ml.models.behavior_model)
            if "app.ml.pipelines" in sys.modules:
                sys.modules.setdefault("ml.pipelines", sys.modules["app.ml.pipelines"])
            sys.modules.setdefault("ml.pipelines.feature_engineering", app.ml.pipelines.feature_engineering)

            self._pipeline = joblib.load(path)
            logger.info(f"Behavior model pipeline loaded from {path}")
            self._loaded = True
        except Exception as exc:
            logger.error(f"Failed to load behavior model from {path}: {exc}")
            self._loaded = False

    def predict(self, payload: Dict[str, Any]) -> Tuple[float, float, List[str]]:
        """
        Returns:
        --------
        anomaly_score : float [0, 1] (higher = more anomalous)
        latency_ms    : float
        risk_factors  : list[str]
        """
        t0 = time.perf_counter()

        risk_factors = self._extract_risk_factors(payload)

        if not self._loaded or self._pipeline is None:
            score = float(np.random.beta(1, 5))
            latency = (time.perf_counter() - t0) * 1000
            return score, latency, risk_factors

        df = self._payload_to_df(payload)

        try:
            raw = self._pipeline.score_samples(df)[0]
            score = float(np.clip(1.0 + raw, 0.0, 1.0))
        except Exception as exc:
            logger.error(f"Behavior prediction error: {exc}")
            score = 0.0

        latency = (time.perf_counter() - t0) * 1000
        return score, latency, risk_factors

    def _extract_risk_factors(self, payload: Dict[str, Any]) -> List[str]:
        factors = []
        if payload.get("is_tor"):
            factors.append("TOR Exit Node Connection")
        if payload.get("is_vpn"):
            factors.append("VPN / Proxy IP Detected")
        if payload.get("device_change"):
            factors.append("Unrecognized Device Fingerprint")
        if payload.get("failed_logins", 0) >= 3:
            factors.append(f"Multiple Failed Login Attempts ({payload['failed_logins']})")
        hour = payload.get("login_hour", 12)
        if hour < 5 or hour >= 23:
            factors.append(f"Off-Hours Session Activity ({hour:02d}:00)")
        speed = payload.get("typing_speed", 5.0)
        if speed > 12.0:
            factors.append("Abnormally High Typing Velocity (Bot Signature)")
        return factors

    @staticmethod
    def _payload_to_df(payload: Dict[str, Any]) -> pd.DataFrame:
        skip = {
            "session_id", "user_id", "ip_address",
            "device_fingerprint", "user_agent",
            "geo_country", "geo_city",
        }
        row = {k: v for k, v in payload.items() if k not in skip}
        return pd.DataFrame([row])
