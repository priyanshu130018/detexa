"""
scripts/train_models.py
─────────────────────────────────────────────────────────────────────────────
Train Credit Fraud Classifier (XGBoost/RF) and Behavioral Anomaly Model.

Usage:
    python scripts/train_models.py [--data path/to/creditcard.csv]
"""

import argparse
import os
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

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

# Enable importing app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import logger
from app.ml.pipelines.feature_engineering import (
    CreditFeatureEngineer,
    BehaviorFeatureEngineer,
)
from app.ml.models.behavior_model import BehaviorPipeline


def generate_synthetic_credit_data(n: int = 10_000) -> pd.DataFrame:
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
    logger.info(f"Synthetic credit data generated: {len(df)} rows, fraud={n_fraud/n:.2%}")
    return df


def generate_synthetic_behavior_data(n: int = 5_000) -> pd.DataFrame:
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
    logger.info(f"Synthetic behavior data generated: {len(df)} rows")
    return df


def train_credit_model(data_path: str | None, output_dir: Path):
    logger.info("── Training Credit Card Fraud Classifier ───────────────────────")
    possible_data_paths = [
        data_path,
        "data/raw/indian_banking_transactions.csv",
        "data/indian_banking_transactions.csv",
        "backend/data/indian_banking_transactions.csv",
        "data/creditcard.csv",
        "backend/data/creditcard.csv",
    ]
    resolved_data_path = next((p for p in possible_data_paths if p and Path(p).exists()), None)

    if resolved_data_path:
        logger.info(f"Loading real dataset from {resolved_data_path}")
        df = pd.read_csv(resolved_data_path)
        if "Time" in df.columns:
            df.drop(columns=["Time"], inplace=True)
    else:
        logger.warning("Dataset not found – generating synthetic dataset for training")
        df = generate_synthetic_credit_data()

    target_col = "Class" if "Class" in df.columns else "class"
    y = df[target_col].values
    X = df.drop(columns=[target_col])

    if "amount" in X.columns and "Amount" not in X.columns:
        X.rename(columns={"amount": "Amount"}, inplace=True)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    feature_eng = CreditFeatureEngineer()
    X_train_t = feature_eng.fit_transform(X_train)
    X_test_t = feature_eng.transform(X_test)

    if SMOTE_AVAILABLE:
        sm = SMOTE(random_state=42, sampling_strategy=0.1)
        X_train_t, y_train = sm.fit_resample(X_train_t, y_train)
        logger.info(f"After SMOTE: {len(X_train_t)} samples")

    if XGB_AVAILABLE:
        logger.info("Using XGBoost Classifier")
        neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
        clf = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            scale_pos_weight=neg / pos if pos > 0 else 1.0,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42,
            n_jobs=-1,
        )
    else:
        logger.info("Using RandomForest Classifier")
        clf = RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

    clf.fit(X_train_t, y_train)

    y_pred = clf.predict(X_test_t)
    y_proba = clf.predict_proba(X_test_t)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    logger.info(f"AUC-ROC Score: {auc:.4f}")
    logger.info("\n" + classification_report(y_test, y_pred))

    pipeline = Pipeline([
        ("features", feature_eng),
        ("classifier", clf),
    ])

    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output_dir / "credit_fraud_pipeline.pkl"
    joblib.dump(pipeline, save_path)
    logger.info(f"Credit fraud pipeline saved -> {save_path}")
    return auc


def train_behavior_model(output_dir: Path):
    logger.info("── Training Behavioral Anomaly Model ──────────────────────────")
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

    pipeline = BehaviorPipeline(feature_eng, clf)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_path = output_dir / "behavior_pipeline.pkl"
    joblib.dump(pipeline, save_path)
    logger.info(f"Behavior anomaly pipeline saved -> {save_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Detexa ML models")
    parser.add_argument("--data", default=None, help="Path to creditcard.csv")
    args = parser.parse_args()

    out_dir = Path(settings.model_path)
    train_credit_model(args.data, out_dir)
    train_behavior_model(out_dir)
    logger.info("All ML models trained and serialized successfully ✓")
