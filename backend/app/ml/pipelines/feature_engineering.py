"""
app/ml/pipelines/feature_engineering.py
─────────────────────────────────────────────────────────────────────────────
Feature engineering transformers for Credit Fraud and Behavior Anomaly models.
"""

from typing import List, Optional
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler

CREDIT_FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]


class CreditFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Transforms PCA features from Kaggle Credit Card dataset by engineering
    interaction terms, log-transforms, amount squares, and L2 norms.
    Caches feature names for reliable downstream SHAP explanations.
    """

    def __init__(self):
        self._scaler = StandardScaler()
        self._feature_names_cache: List[str] = []

    def fit(self, X: pd.DataFrame, y=None):
        df = self._add_features(X.copy())
        cols = self._feature_names(df)
        self._feature_names_cache = cols
        self._scaler.fit(df[cols])
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = self._add_features(X.copy())
        cols = self._feature_names(df)
        if not self._feature_names_cache:
            self._feature_names_cache = cols
        return self._scaler.transform(df[cols])

    # ── Internal Feature Generators ──────────────────────────────────────────

    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Standardize column naming: v1 -> V1, amount -> Amount
        col_map = {c: c.capitalize() if c.lower().startswith("v") else c for c in df.columns}
        if "amount" in col_map:
            col_map["amount"] = "Amount"
        df.rename(columns=col_map, inplace=True)

        if "Amount" in df.columns:
            df["log_amount"] = np.log1p(df["Amount"].clip(lower=0))
            df["amount_sq"] = df["Amount"] ** 2
        else:
            df["Amount"] = 0.0
            df["log_amount"] = 0.0
            df["amount_sq"] = 0.0

        # Fill any missing V columns with 0.0
        for i in range(1, 29):
            col = f"V{i}"
            if col not in df.columns:
                df[col] = 0.0

        # Non-linear interaction terms known to contribute to fraud separation
        for a, b in [("V1", "V2"), ("V3", "V4"), ("V14", "V17")]:
            df[f"{a}_{b}_interaction"] = df[a] * df[b]

        # L2 norm over all V-components
        v_cols = [f"V{i}" for i in range(1, 29)]
        df["v_norm"] = np.sqrt((df[v_cols] ** 2).sum(axis=1))

        return df

    def _feature_names(self, df: pd.DataFrame) -> List[str]:
        base = [f"V{i}" for i in range(1, 29)] + ["Amount"]
        extra = [
            "log_amount",
            "amount_sq",
            "V1_V2_interaction",
            "V3_V4_interaction",
            "V14_V17_interaction",
            "v_norm",
        ]
        return base + extra

    def get_feature_names_out(self, input_features=None) -> List[str]:
        if self._feature_names_cache:
            return self._feature_names_cache
        return [f"V{i}" for i in range(1, 29)] + ["Amount", "log_amount", "amount_sq", "V1_V2_interaction", "V3_V4_interaction", "V14_V17_interaction", "v_norm"]


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
