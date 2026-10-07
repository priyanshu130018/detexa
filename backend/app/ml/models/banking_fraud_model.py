"""
app/ml/models/banking_fraud_model.py
─────────────────────────────────────────────────────────────────────────────
Wrapper around trained XGBoost Indian Banking fraud classifier.
Handles loading, batch/single inference, and TreeSHAP explainability.
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
import warnings
import xgboost as xgb

warnings.filterwarnings("ignore", message=r".*serialized model.*")
warnings.filterwarnings("ignore", message=r".*error_msg\.h.*")
warnings.filterwarnings("ignore", message=r".*Booster\.save_model.*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"xgboost(\..*)?")

from app.core.config import settings
from app.core.logging import logger

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False


class BankingFraudModel:
    MODEL_VERSION = "2.0.0"
    _instance: Optional["BankingFraudModel"] = None

    def __init__(self):
        self._pipeline = None
        self._booster = None
        self._preprocessor = None
        self._explainer = None
        self._loaded = False
        self._feature_names = []

    @classmethod
    def get_instance(cls) -> "BankingFraudModel":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._load()
        return cls._instance

    def _load(self):
        possible_paths = [
            Path(settings.model_path) / "banking_fraud_pipeline.pkl",
            Path("app/ml/saved/banking_fraud_pipeline.pkl"),
            Path("ml/models/saved/banking_fraud_pipeline.pkl"),
            Path("backend/app/ml/saved/banking_fraud_pipeline.pkl"),
            Path(__file__).parent.parent / "saved" / "banking_fraud_pipeline.pkl",
        ]

        pipeline_path = next((p for p in possible_paths if p.exists()), None)

        if not pipeline_path:
            logger.warning(
                f"Banking fraud model not found in paths: {[str(p) for p in possible_paths]}. "
                "Inference will fall back to simulated scores."
            )
            self._loaded = False
            return

        try:
            self._pipeline = joblib.load(pipeline_path)
            self._preprocessor = self._pipeline.named_steps.get("preprocessor")
            clf = self._pipeline.named_steps.get("classifier")

            if clf is not None and hasattr(clf, "get_booster"):
                self._booster = clf.get_booster()

            if self._preprocessor is not None and hasattr(self._preprocessor, "get_feature_names_out"):
                self._feature_names = self._preprocessor.get_feature_names_out()

            if SHAP_AVAILABLE and clf is not None:
                try:
                    self._explainer = shap.TreeExplainer(clf)
                except Exception as e:
                    logger.debug(f"SHAP TreeExplainer build skipped: {e}")
                    self._explainer = None

            self._loaded = True
            logger.info(f"Banking fraud pipeline loaded successfully from {pipeline_path}")
        except Exception as exc:
            logger.error(f"Failed to load banking fraud pipeline: {exc}")
            self._loaded = False

    def predict(self, payload: Dict[str, Any]) -> Tuple[float, Optional[List[Dict[str, Any]]]]:
        """
        Run low-latency inference on a single banking transaction payload.
        Returns: (fraud_score: float [0, 1], shap_top_features: list[dict] | None)
        """
        from app.ml.inference import get_inference_service
        res = get_inference_service().predict(payload)
        return res.fraud_probability, res.shap_drivers

    def predict_batch(self, payloads: List[Dict[str, Any]]) -> List[Tuple[float, Optional[List[Dict[str, Any]]]]]:
        """Run batch inference over a list of banking transaction dictionaries."""
        if not payloads:
            return []
        if not self._loaded or self._pipeline is None:
            return [(0.05, None) for _ in payloads]

        df = pd.DataFrame(payloads)

        try:
            probas = self._pipeline.predict_proba(df)[:, 1]
            scores = [float(np.clip(p, 0.0, 1.0)) for p in probas]
        except Exception as exc:
            logger.error(f"Batch prediction error: {exc}")
            scores = [0.05] * len(payloads)

        results = []
        for i, score in enumerate(scores):
            df_single = df.iloc[[i]]
            shap_feat = self._explain(df_single) if score > 0.3 else None
            results.append((score, shap_feat))
        return results

    def _explain(self, df: pd.DataFrame) -> Optional[List[Dict[str, Any]]]:
        """Compute top risk-driving SHAP features for suspicious transactions."""
        try:
            if self._preprocessor is None:
                return None

            X_trans = self._preprocessor.transform(df)
            feat_names = self._feature_names or [f"f_{j}" for j in range(X_trans.shape[1])]

            # Fast path 1: Native XGBoost TreeSHAP via C++ core
            if self._booster is not None:
                dmat = xgb.DMatrix(X_trans, feature_names=feat_names)
                contribs = self._booster.predict(dmat, pred_contribs=True)
                # Last column of contribs is the bias term
                values = contribs[0, :-1]
            elif self._explainer is not None:
                sv = self._explainer.shap_values(X_trans)
                if isinstance(sv, list):
                    sv = sv[1]
                values = sv[0] if len(sv.shape) > 1 else sv
            else:
                return None

            paired = sorted(
                zip(feat_names, values.tolist()),
                key=lambda x: abs(x[1]),
                reverse=True,
            )
            return [{"feature": name, "shap_value": round(float(val), 5)} for name, val in paired[:10]]
        except Exception as exc:
            logger.debug(f"SHAP explanation failed: {exc}")
            return None

    @staticmethod
    def hash_input(payload: Dict[str, Any]) -> str:
        canon = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canon.encode()).hexdigest()


# Backward compatibility alias
CreditFraudModel = BankingFraudModel
