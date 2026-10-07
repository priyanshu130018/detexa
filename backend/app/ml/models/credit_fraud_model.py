"""
app/ml/models/credit_fraud_model.py
─────────────────────────────────────────────────────────────────────────────
Wrapper around trained XGBoost / Random Forest credit-fraud classifier.
Handles loading, batch/single inference, and SHAP explainability.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.logging import logger

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


class CreditFraudModel:
    MODEL_VERSION = "2.0.0"
    _instance: Optional["CreditFraudModel"] = None

    def __init__(self):
        self._pipeline = None
        self._explainer = None
        self._loaded = False

    @classmethod
    def get_instance(cls) -> "CreditFraudModel":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        possible_paths = [
            Path(settings.model_path) / "credit_fraud_pipeline.pkl",
            Path("app/ml/saved/credit_fraud_pipeline.pkl"),
            Path("ml/models/saved/credit_fraud_pipeline.pkl"),
            Path("backend/app/ml/saved/credit_fraud_pipeline.pkl"),
        ]

        pipeline_path = next((p for p in possible_paths if p.exists()), None)

        if not pipeline_path:
            logger.warning(
                f"Credit fraud model not found in paths: {[str(p) for p in possible_paths]}. "
                "Inference will fall back to simulated scores."
            )
            self._loaded = False
            return

        try:
            self._pipeline = joblib.load(pipeline_path)
            logger.info(f"Credit fraud pipeline loaded from {pipeline_path}")

            if SHAP_AVAILABLE:
                clf = self._pipeline.named_steps.get("classifier")
                if clf is not None:
                    try:
                        self._explainer = shap.TreeExplainer(clf)
                        logger.info("SHAP TreeExplainer initialized successfully")
                    except Exception as e:
                        logger.debug(f"Could not build SHAP TreeExplainer: {e}")
                        self._explainer = None
            self._loaded = True
        except Exception as exc:
            logger.error(f"Failed to load credit fraud pipeline: {exc}")
            self._loaded = False

    def predict(self, payload: Dict[str, Any]) -> Tuple[float, Optional[List[Dict[str, Any]]]]:
        """
        Run low-latency inference on a single transaction payload using FraudInferenceService.
        Returns: (fraud_score: float [0, 1], shap_top_features: list[dict] | None)
        """
        from app.ml.inference import get_inference_service
        res = get_inference_service().predict(payload)
        return res.fraud_probability, res.shap_drivers


    def predict_batch(self, payloads: List[Dict[str, Any]]) -> List[Tuple[float, Optional[List[Dict[str, Any]]]]]:
        """Run batch inference over a list of transaction dictionaries."""
        if not payloads:
            return []
        if not self._loaded or self._pipeline is None:
            return [(float(np.random.beta(1, 9)), None) for _ in payloads]

        dfs = [self._payload_to_df(p) for p in payloads]
        combined = pd.concat(dfs, ignore_index=True)

        try:
            probas = self._pipeline.predict_proba(combined)[:, 1]
            scores = [float(np.clip(p, 0.0, 1.0)) for p in probas]
        except Exception as exc:
            logger.error(f"Batch prediction error: {exc}")
            scores = [0.0] * len(payloads)

        results = []
        for i, score in enumerate(scores):
            df_single = combined.iloc[[i]]
            shap_feat = self._explain(df_single) if (SHAP_AVAILABLE and self._explainer and score > 0.3) else None
            results.append((score, shap_feat))
        return results

    def _explain(self, df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
        try:
            feat_step = self._pipeline.named_steps.get("preprocessor") or self._pipeline.named_steps.get("features")
            if feat_step is None:
                return None
            transformed = feat_step.transform(df)
            sv = self._explainer.shap_values(transformed)
            if isinstance(sv, list):
                sv = sv[1]
            values = sv[0] if len(sv.shape) > 1 else sv

            if hasattr(feat_step, "get_feature_names_out"):
                feature_names = feat_step.get_feature_names_out()
            else:
                feature_names = getattr(
                    feat_step,
                    "_feature_names_cache",
                    [f"V{i}" for i in range(1, 29)] + ["Amount", "log_amount", "amount_sq", "V1_V2_interaction", "V3_V4_interaction", "V14_V17_interaction", "v_norm"]
                )

            paired = sorted(
                zip(feature_names, values.tolist()),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            return [{"feature": name, "shap_value": round(val, 5)} for name, val in paired[:10]]
        except Exception as exc:
            logger.debug(f"SHAP explanation failed: {exc}")
            return None

    @staticmethod
    def _payload_to_df(payload: Dict[str, Any]) -> pd.DataFrame:
        skip = {"merchant", "category", "country", "currency", "user_id"}
        row = {k: v for k, v in payload.items() if k not in skip}
        if "amount" in row and "Amount" not in row:
            row["Amount"] = row.pop("amount")
        normalised = {}
        for k, v in row.items():
            if k.lower().startswith("v") and k[1:].isdigit():
                normalised[f"V{k[1:]}"] = float(v)
            elif k == "Amount":
                normalised["Amount"] = float(v)
            else:
                normalised[k] = v
        return pd.DataFrame([normalised])

    @staticmethod
    def hash_input(payload: Dict[str, Any]) -> str:
        canon = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canon.encode()).hexdigest()
