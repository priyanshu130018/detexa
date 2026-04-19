"""
ml/models/credit_fraud_model.py
─────────────────────────────────────────────────────────────────────────────
Wrapper around the trained XGBoost / Random Forest credit-fraud classifier.
Handles loading, prediction, and SHAP-based explainability.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from core.config import settings
from core.logging import logger

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


class CreditFraudModel:
    """
    Loads the serialised pipeline (feature engineer + classifier) and exposes
    a single `predict` method that returns (fraud_score, shap_values).
    """

    MODEL_VERSION = "1.0.0"
    _instance: Optional["CreditFraudModel"] = None

    def __init__(self):
        self._pipeline = None
        self._explainer = None
        self._feature_names: List[str] = []
        self._loaded = False

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "CreditFraudModel":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load(self):
        model_dir = Path(settings.model_path)
        pipeline_path = model_dir / "credit_fraud_pipeline.pkl"

        if not pipeline_path.exists():
            logger.warning(f"Credit fraud model not found at {pipeline_path}. "
                           "Run scripts/train_models.py first.")
            self._loaded = False
            return

        try:
            self._pipeline = joblib.load(pipeline_path)
            logger.info(f"Credit fraud model loaded from {pipeline_path}")

            # Build SHAP explainer (tree-based or fallback)
            if SHAP_AVAILABLE:
                clf = self._pipeline.named_steps.get("classifier")
                if clf is not None:
                    try:
                        self._explainer = shap.TreeExplainer(clf)
                    except Exception:
                        self._explainer = None
            self._loaded = True
        except Exception as exc:
            logger.error(f"Failed to load credit fraud model: {exc}")
            self._loaded = False

    # ── Predict ───────────────────────────────────────────────────────────────

    def predict(self, payload: Dict[str, Any]) -> Tuple[float, Optional[List[Dict]]]:
        """
        Returns
        -------
        fraud_score : float  [0, 1]
        shap_features : list[dict] | None
        """
        t0 = time.perf_counter()

        if not self._loaded or self._pipeline is None:
            # Fallback: random score for demo / dev
            score = float(np.random.beta(1, 9))
            return score, None

        df = self._payload_to_df(payload)

        try:
            proba = self._pipeline.predict_proba(df)[:, 1]
            score = float(np.clip(proba[0], 0.0, 1.0))
        except Exception as exc:
            logger.error(f"Credit prediction error: {exc}")
            score = 0.0

        shap_features = self._explain(df) if SHAP_AVAILABLE and self._explainer else None

        latency = (time.perf_counter() - t0) * 1000
        logger.debug(f"Credit fraud score={score:.4f} latency={latency:.1f}ms")
        return score, shap_features

    # ── SHAP ──────────────────────────────────────────────────────────────────

    def _explain(self, df: pd.DataFrame) -> Optional[List[Dict]]:
        try:
            transformed = self._pipeline.named_steps["features"].transform(df)
            sv = self._explainer.shap_values(transformed)
            # Binary classification: sv may be list[array, array]
            if isinstance(sv, list):
                sv = sv[1]
            values = sv[0]
            names = getattr(
                self._pipeline.named_steps["features"], "_feature_names_cache",
                [f"f{i}" for i in range(len(values))],
            )
            paired = sorted(
                zip(names, values.tolist()),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            return [{"feature": n, "shap_value": round(v, 5)} for n, v in paired[:10]]
        except Exception as exc:
            logger.debug(f"SHAP explanation failed: {exc}")
            return None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _payload_to_df(payload: Dict[str, Any]) -> pd.DataFrame:
        skip = {"merchant", "category", "country", "user_id"}
        row = {k: v for k, v in payload.items() if k not in skip}
        # Normalise Amount / amount
        if "amount" in row and "Amount" not in row:
            row["Amount"] = row.pop("amount")
        # Normalise V features
        normalised = {}
        for k, v in row.items():
            if k.lower().startswith("v") and k[1:].isdigit():
                normalised[f"V{k[1:]}"] = v
            else:
                normalised[k] = v
        return pd.DataFrame([normalised])

    @staticmethod
    def hash_input(payload: Dict[str, Any]) -> str:
        canon = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canon.encode()).hexdigest()
