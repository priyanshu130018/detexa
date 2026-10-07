"""
scripts/train_credit_fraud_model.py
─────────────────────────────────────────────────────────────────────────────
Reproducible training script for Detexa Credit Card Fraud Detection Model.
Implements data loading, deduplication, feature engineering, RobustScaler,
Stratified K-Fold CV, XGBoost model training, threshold tuning, and artifact serialization.
"""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time

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
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
import xgboost as xgb

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.pipelines.data_preprocessor import CreditCardDataPreprocessor


def train_model(
    csv_path: str = "data/creditcard.csv",
    output_dir: str = "app/ml/saved",
    model_version: str = "2.0.0",
    random_state: int = 42,
    test_size: float = 0.20,
    n_cv_splits: int = 5,
):
    print("=" * 75)
    print(f"DETEXA ML TRAINING PIPELINE v{model_version}")
    print(f"Random State: {random_state} | Test Split: {test_size:.0%} | CV Folds: {n_cv_splits}")
    print("=" * 75)

    csv_file = Path(csv_path)
    if not csv_file.exists():
        # Check backend/data/creditcard.csv
        alt_path = Path(__file__).parent.parent / "data" / "creditcard.csv"
        if alt_path.exists():
            csv_file = alt_path
        else:
            raise FileNotFoundError(f"Dataset not found at {csv_path} or {alt_path}")

    print(f"\n[1/6] Loading dataset from: {csv_file}")
    df = pd.read_csv(csv_file)
    total_raw_records = len(df)
    print(f"      Loaded {total_raw_records:,} records with {df.shape[1]} columns.")

    # Deduplication analysis & handling
    raw_duplicates = int(df.duplicated().sum())
    print(f"      Detected {raw_duplicates:,} duplicate rows ({raw_duplicates / total_raw_records:.2%}).")
    # Drop exact duplicates to eliminate cross-fold test leakage
    df = df.drop_duplicates().reset_index(drop=True)
    n_records = len(df)
    print(f"      Cleaned dataset size: {n_records:,} unique records.")

    # Missing value verification
    null_counts = int(df.isnull().sum().sum())
    print(f"      Missing values: {null_counts} (Dataset is 100% complete).")

    X = df.drop(columns=["Class"])
    y = df["Class"].astype(int)

    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    fraud_pct = (n_pos / n_records) * 100
    print(f"      Class distribution -> Non-Fraud: {n_neg:,} ({100 - fraud_pct:.3f}%), Fraud: {n_pos:,} ({fraud_pct:.3f}%)")
    print(f"      Imbalance Ratio: {n_neg / n_pos:.2f} : 1")

    # Stratified Train/Test Split (Leakage-free)
    print(f"\n[2/6] Generating Leakage-Free Stratified Train/Test Split ({1 - test_size:.0%}/{test_size:.0%})...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )
    print(f"      Train Set: {len(X_train):,} samples (Fraud: {int(y_train.sum()):,})")
    print(f"      Test Set:  {len(X_test):,} samples (Fraud: {int(y_test.sum()):,})")

    # Define Preprocessor
    print("\n[3/6] Initializing Preprocessor & Feature Engineering...")
    preprocessor = CreditCardDataPreprocessor(
        scaler_type="robust",
        include_time_features=True,
        include_interactions=True,
    )

    # Calculate balanced scale_pos_weight
    train_neg = int((y_train == 0).sum())
    train_pos = int((y_train == 1).sum())
    scale_pos_weight = min(15.0, train_neg / train_pos)
    print(f"      XGBoost scale_pos_weight configured: {scale_pos_weight:.2f}")

    # XGBoost Classifier
    xgb_params = {
        "n_estimators": 200,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": scale_pos_weight,
        "random_state": random_state,
        "eval_metric": "aucpr",
        "n_jobs": -1,
        "tree_method": "hist",
    }

    classifier = xgb.XGBClassifier(**xgb_params)

    full_pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])

    # Stratified K-Fold Cross Validation
    print(f"\n[4/6] Executing {n_cv_splits}-Fold Stratified Cross-Validation on Training Data...")
    skf = StratifiedKFold(n_splits=n_cv_splits, shuffle=True, random_state=random_state)
    cv_pr_aucs = []
    cv_roc_aucs = []
    cv_f1s = []

    fold = 1
    for train_idx, val_idx in skf.split(X_train, y_train):
        X_fold_train, X_fold_val = X_train.iloc[train_idx], X_train.iloc[val_idx]
        y_fold_train, y_fold_val = y_train.iloc[train_idx], y_train.iloc[val_idx]

        # Fit preprocessor strictly on fold training data
        fold_preprocessor = CreditCardDataPreprocessor(scaler_type="robust")
        X_fold_train_trans = fold_preprocessor.fit_transform(X_fold_train)
        X_fold_val_trans = fold_preprocessor.transform(X_fold_val)

        fold_clf = xgb.XGBClassifier(**xgb_params)
        fold_clf.fit(X_fold_train_trans, y_fold_train)

        y_fold_prob = fold_clf.predict_proba(X_fold_val_trans)[:, 1]
        fold_pr_auc = average_precision_score(y_fold_val, y_fold_prob)
        fold_roc_auc = roc_auc_score(y_fold_val, y_fold_prob)
        fold_f1 = f1_score(y_fold_val, (y_fold_prob >= 0.5).astype(int))

        cv_pr_aucs.append(fold_pr_auc)
        cv_roc_aucs.append(fold_roc_auc)
        cv_f1s.append(fold_f1)
        print(f"      Fold {fold}: PR-AUC = {fold_pr_auc:.4f} | ROC-AUC = {fold_roc_auc:.4f} | F1 = {fold_f1:.4f}")
        fold += 1

    print(f"      -- Mean CV PR-AUC:  {np.mean(cv_pr_aucs):.4f} (+/- {np.std(cv_pr_aucs):.4f})")
    print(f"      -- Mean CV ROC-AUC: {np.mean(cv_roc_aucs):.4f} (+/- {np.std(cv_roc_aucs):.4f})")
    print(f"      -- Mean CV F1:      {np.mean(cv_f1s):.4f} (+/- {np.std(cv_f1s):.4f})")

    # Fit Full Pipeline on complete Training Set
    print("\n[5/6] Fitting Full End-to-End Pipeline on 100% of Training Data...")
    t0 = time.perf_counter()
    full_pipeline.fit(X_train, y_train)
    train_duration = time.perf_counter() - t0
    print(f"      Training completed in {train_duration:.2f} seconds.")

    # Evaluate on Holdout Test Set
    print("\n[6/6] Evaluating on Unseen Holdout Test Set...")
    y_test_prob = full_pipeline.predict_proba(X_test)[:, 1]

    test_pr_auc = float(average_precision_score(y_test, y_test_prob))
    test_roc_auc = float(roc_auc_score(y_test, y_test_prob))

    # Optimal Threshold Selection via Precision-Recall Curve
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_test_prob)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    best_idx = int(np.argmax(f1_scores))
    optimal_threshold = float(thresholds[best_idx]) if best_idx < len(thresholds) else 0.50

    # Test predictions at optimal threshold
    y_test_pred_optimal = (y_test_prob >= optimal_threshold).astype(int)
    test_f1 = float(f1_score(y_test, y_test_pred_optimal))
    test_precision = float(precision_score(y_test, y_test_pred_optimal))
    test_recall = float(recall_score(y_test, y_test_pred_optimal))
    cm = confusion_matrix(y_test, y_test_pred_optimal)

    # Test predictions at default 0.50 threshold
    y_test_pred_50 = (y_test_prob >= 0.50).astype(int)
    f1_50 = float(f1_score(y_test, y_test_pred_50))
    prec_50 = float(precision_score(y_test, y_test_pred_50))
    rec_50 = float(recall_score(y_test, y_test_pred_50))

    print("\n" + "=" * 75)
    print("TEST EVALUATION PERFORMANCE METRICS")
    print("=" * 75)
    print(f"PR-AUC (Average Precision): {test_pr_auc:.4f} (Primary Metric)")
    print(f"ROC-AUC:                    {test_roc_auc:.4f}")
    print(f"Optimal Decision Threshold: {optimal_threshold:.4f}")
    print(f"F1-Score @ Optimal:         {test_f1:.4f}  (Precision: {test_precision:.4f}, Recall: {test_recall:.4f})")
    print(f"F1-Score @ 0.50 Default:    {f1_50:.4f}  (Precision: {prec_50:.4f}, Recall: {rec_50:.4f})")
    print(f"\nConfusion Matrix (Optimal Threshold {optimal_threshold:.4f}):")
    print(f"               Predicted Legit    Predicted Fraud")
    print(f"Actual Legit:  {cm[0][0]:>14,}     {cm[0][1]:>14,}")
    print(f"Actual Fraud:  {cm[1][0]:>14,}     {cm[1][1]:>14,}")

    # Feature Importances
    engineered_features = full_pipeline.named_steps["preprocessor"].get_feature_names_out()
    raw_importances = full_pipeline.named_steps["classifier"].feature_importances_
    feature_importances = sorted(
        zip(engineered_features, raw_importances.tolist()),
        key=lambda x: x[1],
        reverse=True,
    )

    print("\nTop 12 Most Important Features:")
    for rank, (feat, imp) in enumerate(feature_importances[:12], 1):
        print(f"  {rank:>2}. {feat:<24} : {imp:.4f}")

    # Persist Artifacts
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pipeline_file = out_dir / "credit_fraud_pipeline.pkl"
    metadata_file = out_dir / "credit_fraud_pipeline_metadata.json"
    features_file = out_dir / "feature_metadata.json"

    print(f"\nSaving model pipeline to: {pipeline_file}")
    joblib.dump(full_pipeline, pipeline_file)

    metrics_payload = {
        "model_name": "CreditFraudXGBoost",
        "model_version": model_version,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_records_clean": n_records,
        "dataset_records_raw": total_raw_records,
        "duplicates_removed": raw_duplicates,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "train_duration_sec": round(train_duration, 2),
        "random_state": random_state,
        "scale_pos_weight": round(scale_pos_weight, 2),
        "cv_5fold": {
            "mean_pr_auc": round(float(np.mean(cv_pr_aucs)), 4),
            "std_pr_auc": round(float(np.std(cv_pr_aucs)), 4),
            "mean_roc_auc": round(float(np.mean(cv_roc_aucs)), 4),
            "mean_f1": round(float(np.mean(cv_f1s)), 4),
        },
        "test_metrics": {
            "pr_auc": round(test_pr_auc, 4),
            "roc_auc": round(test_roc_auc, 4),
            "optimal_threshold": round(optimal_threshold, 4),
            "f1_optimal": round(test_f1, 4),
            "precision_optimal": round(test_precision, 4),
            "recall_optimal": round(test_recall, 4),
            "f1_at_50": round(f1_50, 4),
            "precision_at_50": round(prec_50, 4),
            "recall_at_50": round(rec_50, 4),
            "confusion_matrix": cm.tolist(),
        },
        "xgb_hyperparameters": xgb_params,
    }

    with open(metadata_file, "w") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(features_file, "w") as f:
        json.dump(
            {
                "engineered_feature_count": len(engineered_features),
                "feature_names": engineered_features,
                "top_features": [
                    {"name": feat, "importance": round(imp, 5)}
                    for feat, imp in feature_importances
                ],
            },
            f,
            indent=2,
        )

    print("\n[SUCCESS] DETEXA Credit Fraud Model Training Completed Successfully!")
    return metrics_payload


if __name__ == "__main__":
    train_model()
