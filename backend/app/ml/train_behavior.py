"""
backend/app/ml/train_behavior.py
Script to fit and serialize BehaviorPipeline artifact.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
import joblib

from app.ml.pipelines.feature_engineering import BehaviorFeatureEngineer
from app.ml.models.behavior_model import BehaviorPipeline, BehaviorAnomalyModel

def train_and_save():
    np.random.seed(42)
    n_samples = 2000
    data = {
        'login_hour': np.random.randint(0, 24, n_samples),
        'typing_speed': np.random.normal(5.0, 1.5, n_samples),
        'mouse_velocity': np.random.normal(500, 150, n_samples),
        'failed_logins': np.random.choice([0, 1, 2, 3], p=[0.85, 0.1, 0.04, 0.01], size=n_samples),
        'is_vpn': np.random.choice([0, 1], p=[0.9, 0.1], size=n_samples),
        'is_tor': np.random.choice([0, 1], p=[0.98, 0.02], size=n_samples),
        'device_change': np.random.choice([0, 1], p=[0.92, 0.08], size=n_samples),
    }
    df = pd.DataFrame(data)

    eng = BehaviorFeatureEngineer()
    eng.fit(df)
    X_trans = eng.transform(df)

    iso = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
    iso.fit(X_trans)

    pipeline = BehaviorPipeline(eng, iso)
    out_path = Path("app/ml/saved/behavior_pipeline.pkl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, out_path)
    print(f"Saved behavior pipeline to {out_path.resolve()}")

    # Test loading and prediction
    model = BehaviorAnomalyModel()
    model._load()
    test_payload = {
        'login_hour': 14,
        'typing_speed': 5.2,
        'mouse_velocity': 480.0,
        'failed_logins': 0,
        'is_vpn': 0,
        'is_tor': 0,
        'device_change': 0,
    }
    score, latency, factors = model.predict(test_payload)
    print(f"Prediction normal test: score={score:.4f}, latency={latency:.2f}ms, factors={factors}")

    suspicious_payload = {
        'login_hour': 3,
        'typing_speed': 14.2,
        'mouse_velocity': 1200.0,
        'failed_logins': 4,
        'is_vpn': 1,
        'is_tor': 1,
        'device_change': 1,
    }
    score_s, latency_s, factors_s = model.predict(suspicious_payload)
    print(f"Prediction suspicious test: score={score_s:.4f}, latency={latency_s:.2f}ms, factors={factors_s}")

if __name__ == "__main__":
    train_and_save()
