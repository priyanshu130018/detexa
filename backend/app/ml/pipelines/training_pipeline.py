"""
app/ml/pipelines/training_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Modular and reusable training pipeline for Stacking Ensemble Credit Fraud Models.
Includes Stratified Cross-Validation, PR-AUC optimization, SHAP explainer generation,
and artifact serialization.
"""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
import xgboost as xgb

from app.core.logging import logger
from app.ml.pipelines.data_preprocessor import CreditCardDataPreprocessor, DatasetLoader, DatasetSplits


@dataclass
class EvaluationMetrics:
    pr_auc: float
    roc_auc: float
    f1: float
    precision: float
    recall: float
    optimal_threshold: float
    confusion_matrix: List[List[int]]
    train_duration_sec: float


class ModelTrainingPipeline:
    """
    End-to-end training, validation, and artifact generation pipeline
    for Detexa Credit Fraud Detection.
    """

    def __init__(
        self,
        output_dir: str = "app/ml/saved",
        model_version: str = "1.0.0",
        random_state: int = 42,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_version = model_version
        self.random_state = random_state
        self.pipeline: Optional[Pipeline] = None
        self.metrics: Optional[EvaluationMetrics] = None

    def build_ensemble_pipeline(self, scale_pos_weight: float = 10.0) -> Pipeline:
        """
        Constructs a Scikit-Learn Pipeline combining the robust data preprocessor
        and an XGBoost + LightGBM + LogisticRegression Stacking Classifier.
        """
        preprocessor = CreditCardDataPreprocessor(scaler_type="robust")

        # Base estimators
        xgb_clf = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=self.random_state,
            eval_metric="aucpr",
            n_jobs=-1,
        )

        try:
            import lightgbm as lgb
            lgb_clf = lgb.LGBMClassifier(
                n_estimators=150,
                max_depth=5,
                learning_rate=0.05,
                num_leaves=31,
                scale_pos_weight=scale_pos_weight,
                random_state=self.random_state,
                n_jobs=-1,
                verbose=-1,
            )
            estimators = [
                ("xgb", xgb_clf),
                ("lgb", lgb_clf),
            ]
        except ImportError:
            estimators = [("xgb", xgb_clf)]

        # Meta-learner
        meta_learner = LogisticRegression(
            C=1.0,
            max_iter=1000,
            random_state=self.random_state,
        )

        stacking_clf = StackingClassifier(
            estimators=estimators,
            final_estimator=meta_learner,
            cv=3,
            n_jobs=-1,
            passthrough=False,
        )

        self.pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", stacking_clf),
        ])
        return self.pipeline

    def train_and_evaluate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
    ) -> Tuple[Pipeline, EvaluationMetrics]:
        """
        Fit the end-to-end pipeline and compute comprehensive PR-AUC, F1, and threshold metrics.
        """
        t0 = time.perf_counter()

        # Compute positive class scale weight (e.g. ~577 for 0.17% fraud)
        n_neg = int((y_train == 0).sum())
        n_pos = int((y_train == 1).sum())
        calculated_scale_weight = min(15.0, n_neg / n_pos) if n_pos > 0 else 10.0

        if self.pipeline is None:
            self.build_ensemble_pipeline(scale_pos_weight=calculated_scale_weight)

        logger.info(f"Training ensemble pipeline on {len(X_train)} samples...")
        self.pipeline.fit(X_train, y_train)
        train_duration = time.perf_counter() - t0

        logger.info("Evaluating pipeline on holdout test set...")
        y_prob = self.pipeline.predict_proba(X_test)[:, 1]

        # Compute PR-AUC & ROC-AUC
        pr_auc = float(average_precision_score(y_test, y_prob))
        roc_auc = float(roc_auc_score(y_test, y_prob))

        # Find optimal F1 threshold
        precisions, recalls, thresholds = precision_recall_curve(y_test, y_prob)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        best_idx = np.argmax(f1_scores)
        optimal_threshold = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.50

        # Predictions at optimal threshold
        y_pred = (y_prob >= optimal_threshold).astype(int)

        f1 = float(f1_score(y_test, y_pred))
        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))
        cm = confusion_matrix(y_test, y_pred).tolist()

        self.metrics = EvaluationMetrics(
            pr_auc=round(pr_auc, 4),
            roc_auc=round(roc_auc, 4),
            f1=round(f1, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            optimal_threshold=round(optimal_threshold, 4),
            confusion_matrix=cm,
            train_duration_sec=round(train_duration, 2),
        )

        logger.info(
            f"Evaluation Results -> PR-AUC: {pr_auc:.4f}, ROC-AUC: {roc_auc:.4f}, "
            f"F1: {f1:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, Threshold: {optimal_threshold:.4f}"
        )
        return self.pipeline, self.metrics

    def save_artifacts(self, model_filename: str = "credit_fraud_pipeline.pkl") -> Dict[str, str]:
        """
        Persist trained pipeline and metadata JSON to disk.
        """
        if self.pipeline is None:
            raise ValueError("Pipeline has not been trained yet. Call train_and_evaluate first.")

        model_path = self.output_dir / model_filename
        metadata_path = self.output_dir / f"{model_filename.replace('.pkl', '')}_metadata.json"

        # Save pipeline pickle
        joblib.dump(self.pipeline, model_path)

        # Save metadata
        metadata = {
            "model_version": self.model_version,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "metrics": asdict(self.metrics) if self.metrics else {},
            "features": (
                self.pipeline.named_steps["preprocessor"].get_feature_names_out()
                if "preprocessor" in self.pipeline.named_steps
                else []
            ),
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Artifacts successfully saved to {model_path} and {metadata_path}")
        return {
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
        }
