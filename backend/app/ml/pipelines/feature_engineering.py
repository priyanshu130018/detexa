"""
app/ml/pipelines/feature_engineering.py
─────────────────────────────────────────────────────────────────────────────
Feature engineering transformers for Indian Banking Fraud and Behavior Anomaly models.
"""

from typing import List, Optional
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from app.ml.pipelines.data_preprocessor import (
    CATEGORICAL_BANKING_FEATURES,
    DEFAULT_FEATURE_VALUES,
    NUMERIC_BANKING_FEATURES,
    BankingDataPreprocessor,
)


class BankingFeatureEngineer(BankingDataPreprocessor):
    """
    Transforms raw Indian banking transaction records into full numeric & one-hot encoded
    vectors for training and real-time inference.
    """
    pass


# Backward compatibility alias
CreditFeatureEngineer = BankingFeatureEngineer


# ── Behavior Features ────────────────────────────────────────────────────────

BEHAVIOR_FEATURES = [
    "login_hour",
    "typing_speed",
    "mouse_velocity",
    "failed_logins",
    "is_vpn",
    "is_tor",
    "device_change",
]


class BehaviorFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Normalizes numerical signals and constructs composite risk indicators
    for the Isolation Forest anomaly detector.
    """

    def __init__(self):
        self._scaler = StandardScaler()
        self._feature_names_cache: List[str] = []

    def fit(self, X: pd.DataFrame, y=None):
        df = self._add_features(X.copy())
        cols = BEHAVIOR_FEATURES + self._extra_cols()
        self._feature_names_cache = cols
        self._scaler.fit(df[cols])
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = self._add_features(X.copy())
        cols = BEHAVIOR_FEATURES + self._extra_cols()
        if not getattr(self, "_feature_names_cache", None):
            self._feature_names_cache = cols
        return self._scaler.transform(df[cols])

    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        for f in BEHAVIOR_FEATURES:
            if f not in df.columns:
                df[f] = 0.0

        if "login_hour" in df.columns:
            df["is_night_login"] = df["login_hour"].apply(
                lambda h: 1.0 if (h < 6 or h >= 22) else 0.0
            )
        else:
            df["is_night_login"] = 0.0

        is_vpn = df["is_vpn"].astype(int)
        is_tor = df["is_tor"].astype(int)
        device_change = df["device_change"].astype(int)
        df["risk_combo"] = is_vpn + (is_tor * 2) + device_change

        return df

    def _extra_cols(self) -> List[str]:
        return ["is_night_login", "risk_combo"]

    def get_feature_names_out(self, input_features=None) -> List[str]:
        return BEHAVIOR_FEATURES + self._extra_cols()
