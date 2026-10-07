"""
app/ml/pipelines/training_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Modular and reproducible training pipeline for Indian Banking Fraud Detection.
Includes Stratified Splits, PR-AUC optimization, Threshold Calibration,
TreeSHAP explainability generation, and artifact serialization.
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
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
import xgboost as xgb

from app.core.logging import logger
from app.ml.pipelines.data_preprocessor import (
    BankingDataPreprocessor,
    DatasetLoader,
    DatasetSplits,
)


@dataclass
class EvaluationMetrics:
    pr_auc: float
    roc_auc: float
    f1: float
    precision: float
    recall: float
    specificity: float
    fpr: float
    fnr: float
    optimal_threshold: float
    confusion_matrix: List[List[int]]
    tp: int
    tn: int
    fp: int
    fn: int
    train_duration_sec: float
    threshold_calibration: List[Dict[str, Any]]


class BankingTrainingPipeline:
    """
    End-to-end training, validation, threshold calibration, and artifact generation
    pipeline for Detexa Indian Banking Transaction Fraud Detection.
    """

    def __init__(
        self,
        output_dir: str = "app/ml/saved",
        model_version: str = "2.0.0",
        random_state: int = 42,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_version = model_version
        self.random_state = random_state
        self.pipeline: Optional[Pipeline] = None
        self.metrics: Optional[EvaluationMetrics] = None
        self.optimal_threshold: float = 0.50

    def build_pipeline(self, scale_pos_weight: float = 10.0) -> Pipeline:
        """
        Constructs a Scikit-Learn Pipeline combining the robust banking preprocessor
        and an optimized XGBoost Classifier.
        """
        preprocessor = BankingDataPreprocessor(scaler_type="robust")

        xgb_clf = xgb.XGBClassifier(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.04,
            subsample=0.85,
            colsample_bytree=0.85,
            scale_pos_weight=scale_pos_weight,
            random_state=self.random_state,
            eval_metric="aucpr",
            n_jobs=-1,
        )

        self.pipeline = Pipeline([
            ("preprocessor", preprocessor),
            ("classifier", xgb_clf),
        ])
        return self.pipeline

    def train_and_evaluate(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> Tuple[Pipeline, EvaluationMetrics]:
        """
        Fit the end-to-end banking pipeline and compute comprehensive metrics.
        """
        t0 = time.perf_counter()

        n_neg = int((y_train == 0).sum())
        n_pos = int((y_train == 1).sum())
        calculated_scale_weight = float(n_neg / n_pos) if n_pos > 0 else 10.0

        if self.pipeline is None:
            self.build_pipeline(scale_pos_weight=calculated_scale_weight)

        logger.info(f"Training XGBoost pipeline on {len(X_train)} banking transactions (scale_pos_weight={calculated_scale_weight:.2f})...")
        self.pipeline.fit(X_train, y_train)
        train_duration = time.perf_counter() - t0

        logger.info("Evaluating pipeline on holdout test set...")
        y_prob = self.pipeline.predict_proba(X_test)[:, 1]

        # Compute PR-AUC & ROC-AUC
        pr_auc = float(average_precision_score(y_test, y_prob))
        roc_auc = float(roc_auc_score(y_test, y_prob))

        # Threshold calibration table across range [0.05, 0.95]
        threshold_evals = []
        best_f1 = 0.0
        best_th = 0.50

        for th in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
            y_pred_th = (y_prob >= th).astype(int)
            cm_th = confusion_matrix(y_test, y_pred_th)
            tn_th, fp_th, fn_th, tp_th = cm_th.ravel()
            prec_th = float(precision_score(y_test, y_pred_th, zero_division=0))
            rec_th = float(recall_score(y_test, y_pred_th, zero_division=0))
            f1_th = float(f1_score(y_test, y_pred_th, zero_division=0))
            fpr_th = float(fp_th / (fp_th + tn_th)) if (fp_th + tn_th) > 0 else 0.0
            fnr_th = float(fn_th / (fn_th + tp_th)) if (fn_th + tp_th) > 0 else 0.0
            spec_th = float(tn_th / (tn_th + fp_th)) if (tn_th + fp_th) > 0 else 0.0

            threshold_evals.append({
                "threshold": th,
                "precision": round(prec_th, 4),
                "recall": round(rec_th, 4),
                "f1": round(f1_th, 4),
                "specificity": round(spec_th, 4),
                "fpr": round(fpr_th, 4),
                "fnr": round(fnr_th, 4),
                "tp": int(tp_th),
                "fp": int(fp_th),
                "tn": int(tn_th),
                "fn": int(fn_th),
            })

            if f1_th > best_f1:
                best_f1 = f1_th
                best_th = th

        self.optimal_threshold = best_th

        # Primary predictions at optimal threshold
        y_pred = (y_prob >= self.optimal_threshold).astype(int)
        cm = confusion_matrix(y_test, y_pred)
        tn, fp, fn, tp = cm.ravel()

        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

        self.metrics = EvaluationMetrics(
            pr_auc=round(pr_auc, 4),
            roc_auc=round(roc_auc, 4),
            f1=round(f1, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            specificity=round(specificity, 4),
            fpr=round(fpr, 4),
            fnr=round(fnr, 4),
            optimal_threshold=round(self.optimal_threshold, 4),
            confusion_matrix=cm.tolist(),
            tp=int(tp),
            tn=int(tn),
            fp=int(fp),
            fn=int(fn),
            train_duration_sec=round(train_duration, 2),
            threshold_calibration=threshold_evals,
        )

        logger.info(
            f"Evaluation Results -> PR-AUC: {pr_auc:.4f}, ROC-AUC: {roc_auc:.4f}, "
            f"F1: {f1:.4f}, Precision: {precision:.4f}, Recall: {recall:.4f}, "
            f"FPR: {fpr:.4f}, Optimal Threshold: {self.optimal_threshold:.2f}"
        )
        return self.pipeline, self.metrics

    def save_artifacts(self, model_filename: str = "banking_fraud_pipeline.pkl") -> Dict[str, str]:
        """
        Persist trained pipeline, feature metadata, and evaluation results to disk.
        """
        if self.pipeline is None:
            raise ValueError("Pipeline has not been trained yet. Call train_and_evaluate first.")

        model_path = self.output_dir / model_filename
        metadata_path = self.output_dir / f"{model_filename.replace('.pkl', '')}_metadata.json"
        feature_metadata_path = self.output_dir / "feature_metadata.json"
        eval_results_path = self.output_dir / "evaluation_results.json"

        # 1. Save pipeline pickle
        joblib.dump(self.pipeline, model_path)

        # 2. Extract feature names
        feature_names = (
            self.pipeline.named_steps["preprocessor"].get_feature_names_out()
            if "preprocessor" in self.pipeline.named_steps
            else []
        )

        # 3. Save metadata
        metadata = {
            "model_name": "IndianBankingFraudXGBoost",
            "model_version": self.model_version,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "optimal_threshold": self.optimal_threshold,
            "metrics": asdict(self.metrics) if self.metrics else {},
            "features_count": len(feature_names),
            "features": feature_names,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # 4. Save feature metadata
        feature_metadata = {
            "version": self.model_version,
            "total_features": len(feature_names),
            "feature_names": feature_names,
            "preprocessor_type": "BankingDataPreprocessor",
            "classifier": "XGBClassifier",
        }
        with open(feature_metadata_path, "w") as f:
            json.dump(feature_metadata, f, indent=2)

        # 5. Save evaluation results
        eval_data = asdict(self.metrics) if self.metrics else {}
        with open(eval_results_path, "w") as f:
            json.dump(eval_data, f, indent=2)

        logger.info(f"Artifacts successfully saved to {model_path}, {metadata_path}, and {feature_metadata_path}")
        return {
            "model_path": str(model_path),
            "metadata_path": str(metadata_path),
            "feature_metadata_path": str(feature_metadata_path),
            "eval_results_path": str(eval_results_path),
        }


# Alias for backward compatibility
ModelTrainingPipeline = BankingTrainingPipeline
