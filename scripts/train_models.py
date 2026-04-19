"""
scripts/train_models.py
─────────────────────────────────────────────────────────────────────────────
Train the credit-card fraud classifier and the behavioural anomaly detector.

Usage
-----
    python scripts/train_models.py [--data path/to/creditcard.csv]

If the Kaggle CSV is not provided, synthetic data is generated for demo
purposes. Download the real dataset from:
    https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud
"""

import argparse
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBClassifier
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import settings
from core.logging import logger
from ml.pipelines.feature_engineering import (
    CreditFeatureEngineer, BehaviorFeatureEngineer,
)
from ml.models.behavior_model import BehaviorPipeline


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_synthetic_credit_data(n: int = 10_000) -> pd.DataFrame:
    """Generate synthetic credit-card data for development."""
    rng = np.random.default_rng(42)
    n_fraud = int(n * 0.017)

    rows = []
    for is_fraud in [0, 1]:
        count = n_fraud if is_fraud else n - n_fraud
        for _ in range(count):
            row = {"Class": is_fraud, "Amount": rng.lognormal(3, 1.5)}
            for i in range(1, 29):
                mu = rng.uniform(-2, 2) if is_fraud else 0
                row[f"V{i}"] = rng.normal(mu, 1)
            rows.append(row)

    df = pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)
    logger.info(f"Synthetic credit data: {len(df)} rows, fraud rate={n_fraud/n:.2%}")
    return df


def generate_synthetic_behavior_data(n: int = 5_000) -> pd.DataFrame:
    """Generate synthetic behavioural log data."""
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "login_hour": rng.integers(0, 24, n),
        "typing_speed": rng.exponential(4, n),
        "mouse_velocity": rng.exponential(200, n),
        "failed_logins": rng.integers(0, 6, n),
        "is_vpn": rng.integers(0, 2, n),
        "is_tor": rng.integers(0, 2, n),
        "device_change": rng.integers(0, 2, n),
    })
    logger.info(f"Synthetic behavior data: {len(df)} rows")
    return df


# ── Credit Fraud Training ─────────────────────────────────────────────────────

def train_credit_model(data_path: str | None, output_dir: Path):
    logger.info("── Training Credit Fraud Model ──────────────────────────")

    if data_path and Path(data_path).exists():
        logger.info(f"Loading Kaggle dataset from {data_path}")
        df = pd.read_csv(data_path)
        # Drop 'Time' column if present (Kaggle dataset artifact)
        if "Time" in df.columns:
            df.drop(columns=["Time"], inplace=True)
    else:
        logger.warning("Kaggle CSV not found – using synthetic data")
        df = generate_synthetic_credit_data()

    # Feature / label split
    target_col = "Class" if "Class" in df.columns else "class"
    y = df[target_col].values
    X = df.drop(columns=[target_col])

    # Ensure Amount column exists
    if "amount" in X.columns and "Amount" not in X.columns:
        X.rename(columns={"amount": "Amount"}, inplace=True)

    logger.info(f"Dataset: {len(X)} rows | fraud={y.sum()} ({y.mean():.2%})")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Feature engineering
    feature_eng = CreditFeatureEngineer()
    X_train_t = feature_eng.fit_transform(X_train)
    X_test_t = feature_eng.transform(X_test)

    # Handle class imbalance
    if SMOTE_AVAILABLE:
        sm = SMOTE(random_state=42, sampling_strategy=0.1)
        X_train_t, y_train = sm.fit_resample(X_train_t, y_train)
        logger.info(f"After SMOTE: {len(X_train_t)} samples")

    # Choose classifier
    if XGB_AVAILABLE:
        logger.info("Using XGBoost classifier")
        neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
        clf = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            scale_pos_weight=neg / pos,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    else:
        logger.info("XGBoost not available – using RandomForest")
        clf = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

    clf.fit(X_train_t, y_train)

    # Evaluate
    y_pred = clf.predict(X_test_t)
    y_proba = clf.predict_proba(X_test_t)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    logger.info(f"AUC-ROC: {auc:.4f}")
    logger.info("\n" + classification_report(y_test, y_pred))

    # Build sklearn Pipeline so feature_eng + clf are saved together
    pipeline = Pipeline([
        ("features", feature_eng),
        ("classifier", clf),
    ])
    # Re-attach already-fitted steps (avoid double-fit)
    pipeline.steps[0] = ("features", feature_eng)
    pipeline.steps[1] = ("classifier", clf)

    # Save (skip the fit step – manually set fitted attribute)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output_dir / "credit_fraud_pipeline.pkl"
    joblib.dump(pipeline, save_path)
    logger.info(f"Credit fraud pipeline saved → {save_path}")
    return auc


# ── Behaviour Anomaly Training ────────────────────────────────────────────────

def train_behavior_model(output_dir: Path):
    logger.info("── Training Behaviour Anomaly Model ─────────────────────")
    df = generate_synthetic_behavior_data()

    feature_eng = BehaviorFeatureEngineer()
    X = feature_eng.fit_transform(df)

    clf = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X)

    # Wrap as simple pipeline (feature_eng already fitted)
    pipeline = BehaviorPipeline(feature_eng, clf)
    save_path = output_dir / "behavior_pipeline.pkl"
    joblib.dump(pipeline, save_path)
    logger.info(f"Behaviour pipeline saved → {save_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Detexa ML models")
    parser.add_argument(
        "--data", default=None,
        help="Path to Kaggle creditcard.csv  (optional; synthetic data used if omitted)"
    )
    args = parser.parse_args()

    output_dir = Path(settings.model_path)
    train_credit_model(args.data, output_dir)
    train_behavior_model(output_dir)
    logger.info("All models trained and saved successfully ✓")
