"""
scripts/train_banking_fraud_model.py
─────────────────────────────────────────────────────────────────────────────
Reproducible training script for Detexa Indian Banking Transaction Fraud Detection Model.
Implements data loading, temporal ordering, zero-leakage feature engineering,
Stratified K-Fold CV, XGBoost model training, threshold calibration,
TreeSHAP explainability, and artifact serialization.
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

from app.ml.pipelines.data_preprocessor import (
    CATEGORICAL_BANKING_FEATURES,
    NUMERIC_BANKING_FEATURES,
    BankingDataPreprocessor,
)
from app.ml.pipelines.training_pipeline import BankingTrainingPipeline


def train_banking_model(
    csv_path: str = "backend/data/raw/indian_banking_transactions.csv",
    output_dir: str = "app/ml/saved",
    model_version: str = "2.0.0",
    random_state: int = 42,
    test_size: float = 0.15,
    val_size: float = 0.15,
):
    print("=" * 80)
    print(f"DETEXA INDIAN BANKING FRAUD ML TRAINING PIPELINE v{model_version}")
    print(f"Random State: {random_state} | Test Split: {test_size:.0%} | Val Split: {val_size:.0%}")
    print("=" * 80)

    # 1. Resolve CSV dataset path
    possible_paths = [
        Path(csv_path),
        Path("backend/data/raw/indian_banking_transactions.csv"),
        Path("data/raw/indian_banking_transactions.csv"),
        Path(__file__).parent.parent / "data" / "raw" / "indian_banking_transactions.csv",
        Path(__file__).parent.parent.parent / "backend" / "data" / "raw" / "indian_banking_transactions.csv",
    ]
    csv_file = next((p for p in possible_paths if p.exists()), None)
    if not csv_file:
        raise FileNotFoundError(f"Indian banking dataset not found in candidate paths: {[str(p) for p in possible_paths]}")

    print(f"\n[1/6] Loading Indian Banking Dataset from: {csv_file}")
    t0_load = time.perf_counter()
    df = pd.read_csv(csv_file)
    n_raw = len(df)
    print(f"      Loaded {n_raw:,} records with {df.shape[1]} columns in {time.perf_counter() - t0_load:.2f}s.")

    # 2. Chronological Ordering & Zero-Leakage Feature Engineering
    print("\n[2/6] Chronological sorting & feature engineering (strictly preventing leakage)...")
    df['datetime'] = pd.to_datetime(df['transaction_date'] + ' ' + df['transaction_time'])
    df = df.sort_values(['datetime', 'transaction_id']).reset_index(drop=True)

    # Calculate expanding historical features strictly prior to current transaction
    df['cust_txn_count_prior'] = df.groupby('customer_id').cumcount().astype(float)
    cum_sum = df.groupby('customer_id')['transaction_amount'].cumsum()
    prior_sum = cum_sum - df['transaction_amount']
    df['cust_avg_amount_prior'] = np.where(
        df['cust_txn_count_prior'] > 0,
        prior_sum / np.maximum(df['cust_txn_count_prior'], 1),
        df['transaction_amount']
    )
    df['cust_amount_diff_from_avg'] = df['transaction_amount'] - df['cust_avg_amount_prior']
    df['cust_amount_ratio_to_avg'] = df['transaction_amount'] / (df['cust_avg_amount_prior'] + 1.0)

    prev_time = df.groupby('customer_id')['datetime'].shift(1)
    df['cust_time_since_last_txn_hours'] = ((df['datetime'] - prev_time).dt.total_seconds() / 3600.0).fillna(168.0)

    prev_channel = df.groupby('customer_id')['channel'].shift(1)
    df['cust_channel_change'] = np.where(prev_channel.isna(), 0.0, (df['channel'] != prev_channel).astype(float))

    prev_type = df.groupby('customer_id')['transaction_type'].shift(1)
    df['cust_type_change'] = np.where(prev_type.isna(), 0.0, (df['transaction_type'] != prev_type).astype(float))

    target = 'is_fraud'
    y = df[target].astype(int)
    X = df.drop(columns=[target, 'datetime'])

    n_neg = int((y == 0).sum())
    n_pos = int((y == 1).sum())
    fraud_pct = (n_pos / n_raw) * 100
    print(f"      Class distribution -> Legit: {n_neg:,} ({100 - fraud_pct:.3f}%), Fraud: {n_pos:,} ({fraud_pct:.3f}%)")
    print(f"      Class imbalance ratio: {n_neg / n_pos:.2f} : 1")

    # 3. Stratified Train / Validation / Test Split
    print(f"\n[3/6] Generating Stratified Train/Val/Test Split ({1 - test_size - val_size:.0%}/{val_size:.0%}/{test_size:.0%})...")
    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=random_state
    )
    val_relative_ratio = val_size / (1.0 - test_size)
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=val_relative_ratio, stratify=y_train_full, random_state=random_state
    )
    print(f"      Train Set: {len(X_train):,} samples (Fraud: {int(y_train.sum()):,})")
    print(f"      Val Set:   {len(X_val):,} samples (Fraud: {int(y_val.sum()):,})")
    print(f"      Test Set:  {len(X_test):,} samples (Fraud: {int(y_test.sum()):,})")

    # 4. Training Pipeline Execution
    print("\n[4/6] Initializing Banking Training Pipeline & Fitting on Training Data...")
    pipeline_builder = BankingTrainingPipeline(
        output_dir=output_dir,
        model_version=model_version,
        random_state=random_state,
    )

    pipeline, metrics = pipeline_builder.train_and_evaluate(
        X_train=X_train,
        y_train=y_train,
        X_test=X_test,
        y_test=y_test,
        X_val=X_val,
        y_val=y_val,
    )

    # 5. Threshold Calibration Table Display
    print("\n[5/6] Threshold Calibration Table:")
    print(f"{'Threshold':>10} | {'Precision':>10} | {'Recall':>10} | {'F1':>10} | {'FPR':>10} | {'FNR':>10} | {'TP':>6} | {'FP':>6} | {'TN':>6} | {'FN':>6}")
    print("-" * 105)
    for row in metrics.threshold_calibration:
        print(f"{row['threshold']:10.2f} | {row['precision']:10.4f} | {row['recall']:10.4f} | {row['f1']:10.4f} | {row['fpr']:10.4f} | {row['fnr']:10.4f} | {row['tp']:6d} | {row['fp']:6d} | {row['tn']:6d} | {row['fn']:6d}")

    print("\n" + "=" * 80)
    print("TEST EVALUATION PERFORMANCE METRICS")
    print("=" * 80)
    print(f"ROC-AUC:                    {metrics.roc_auc:.4f}")
    print(f"PR-AUC (Average Precision): {metrics.pr_auc:.4f}")
    print(f"Selected Optimal Threshold: {metrics.optimal_threshold:.2f}")
    print(f"Precision:                  {metrics.precision:.4f}")
    print(f"Recall:                     {metrics.recall:.4f}")
    print(f"F1-Score:                   {metrics.f1:.4f}")
    print(f"Specificity:                {metrics.specificity:.4f}")
    print(f"False Positive Rate (FPR):  {metrics.fpr:.4f}")
    print(f"False Negative Rate (FNR):  {metrics.fnr:.4f}")
    print(f"Confusion Matrix (TP, TN, FP, FN): TP={metrics.tp}, TN={metrics.tn}, FP={metrics.fp}, FN={metrics.fn}")

    # 6. Artifact Serialization
    print("\n[6/6] Exporting Production Model Artifacts...")
    saved_paths = pipeline_builder.save_artifacts("banking_fraud_pipeline.pkl")
    print(f"      Pipeline: {saved_paths['model_path']}")
    print(f"      Metadata: {saved_paths['metadata_path']}")
    print(f"      Features: {saved_paths['feature_metadata_path']}")

    print("\n[SUCCESS] Indian Banking Fraud ML Model Pipeline Trained & Exported Successfully!")
    return metrics


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "app/ml/saved"
    train_banking_model(output_dir=out)
