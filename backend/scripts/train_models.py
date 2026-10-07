"""
scripts/train_models.py
─────────────────────────────────────────────────────────────────────────────
Train Indian Banking Fraud Classifier (XGBoost) and Behavioral Anomaly Model.

Usage:
    python scripts/train_models.py
"""

import argparse
import os
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Enable importing app.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.logging import logger
from app.ml.pipelines.feature_engineering import BehaviorFeatureEngineer
from app.ml.models.behavior_model import BehaviorPipeline
from scripts.train_banking_fraud_model import train_banking_model


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
    logger.info(f"Behavior training data generated: {len(df)} rows")
    return df


def train_behavior_model(output_dir: Path):
    logger.info("── Training Behavioral Anomaly Model (Isolation Forest) ──────")
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
    parser.add_argument("--data", default="backend/data/raw/indian_banking_transactions.csv", help="Path to dataset")
    args = parser.parse_args()

    out_dir = Path(__file__).parent.parent / "app" / "ml" / "saved"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Train Indian Banking Fraud Model
    train_banking_model(csv_path=args.data, output_dir=str(out_dir))

    # 2. Train Behavioral Anomaly Model
    train_behavior_model(out_dir)

    logger.info("All Detexa ML models trained and serialized successfully ✓")
