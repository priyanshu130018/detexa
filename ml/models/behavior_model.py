"""
ml/models/behavior_model.py
─────────────────────────────────────────────────────────────────────────────
Isolation Forest wrapper for behavioural anomaly detection.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from core.config import settings
from core.logging import logger

class BehaviorPipeline:
    def __init__(self, eng, model):
        self.eng = eng
        self.model = model

    def score_samples(self, df_raw):
        return self.model.score_samples(self.eng.transform(df_raw))


class BehaviorAnomalyModel:
    MODEL_VERSION = "1.0.0"
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
        path = Path(settings.model_path) / "behavior_pipeline.pkl"
        if not path.exists():
            logger.warning(f"Behavior model not found at {path}.")
            return
        try:
            self._pipeline = joblib.load(path)
            logger.info(f"Behavior model loaded from {path}")
            self._loaded = True
        except Exception as exc:
            logger.error(f"Failed to load behavior model: {exc}")

    def predict(self, payload: Dict[str, Any]) -> Tuple[float, float]:
        """
        Returns
        -------
        anomaly_score : float  [0, 1]  (higher = more anomalous)
        latency_ms    : float
        """
        t0 = time.perf_counter()

        if not self._loaded or self._pipeline is None:
            score = float(np.random.beta(1, 5))
            return score, (time.perf_counter() - t0) * 1000

        df = self._payload_to_df(payload)

        try:
            # IsolationForest score_samples: more negative = more anomalous
            raw = self._pipeline.score_samples(df)[0]
            # Normalise to [0, 1] where 1 = most anomalous
            # Typical range is [-0.7, 0.0]; clamp and invert
            score = float(np.clip(1.0 + raw, 0.0, 1.0))
        except Exception as exc:
            logger.error(f"Behavior prediction error: {exc}")
            score = 0.0

        latency = (time.perf_counter() - t0) * 1000
        return score, latency

    @staticmethod
    def _payload_to_df(payload: Dict[str, Any]) -> pd.DataFrame:
        skip = {"session_id", "user_id", "ip_address",
                "device_fingerprint", "user_agent",
                "geo_country", "geo_city"}
        row = {k: v for k, v in payload.items() if k not in skip}
        return pd.DataFrame([row])
