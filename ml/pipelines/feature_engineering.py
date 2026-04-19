"""
ml/pipelines/feature_engineering.py
─────────────────────────────────────────────────────────────────────────────
Feature engineering for both the credit-card fraud model and the
behavioural anomaly model.
"""

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.preprocessing import StandardScaler


# ── Credit-card features ──────────────────────────────────────────────────────

CREDIT_FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]


class CreditFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Adds interaction and derived features on top of the raw PCA columns
    from the Kaggle Credit Card Fraud dataset.
    """

    def __init__(self):
        self._scaler = StandardScaler()

    def fit(self, X: pd.DataFrame, y=None):
        df = self._add_features(X.copy())
        self._scaler.fit(df[self._feature_names(df)])
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = self._add_features(X.copy())
        return self._scaler.transform(df[self._feature_names(df)])

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Normalise column names
        col_map = {c: c.capitalize() if c.lower().startswith("v") else c for c in df.columns}
        df.rename(columns=col_map, inplace=True)

        if "Amount" in df.columns:
            df["log_amount"] = np.log1p(df["Amount"])
            df["amount_sq"] = df["Amount"] ** 2

        # Key interactions known from literature
        for a, b in [("V1", "V2"), ("V3", "V4"), ("V14", "V17")]:
            if a in df.columns and b in df.columns:
                df[f"{a}_{b}_interaction"] = df[a] * df[b]

        # L2 norm of all V features present
        v_cols = [c for c in df.columns if c.startswith("V") and c[1:].isdigit()]
        if v_cols:
            df["v_norm"] = np.sqrt((df[v_cols] ** 2).sum(axis=1))

        return df

    def _feature_names(self, df: pd.DataFrame):
        base = [c for c in df.columns if c.startswith("V") or c == "Amount"]
        extra = [c for c in df.columns if c in (
            "log_amount", "amount_sq", "V1_V2_interaction",
            "V3_V4_interaction", "V14_V17_interaction", "v_norm",
        )]
        return base + extra

    def get_feature_names_out(self, input_features=None):
        # For SHAP compatibility
        return self._feature_names_cache if hasattr(self, "_feature_names_cache") else []


# ── Behaviour features ────────────────────────────────────────────────────────

BEHAVIOR_FEATURES = [
    "login_hour", "typing_speed", "mouse_velocity",
    "failed_logins", "is_vpn", "is_tor", "device_change",
]


class BehaviorFeatureEngineer(BaseEstimator, TransformerMixin):
    """
    Prepares numerical features for the Isolation Forest anomaly detector.
    """

    def __init__(self):
        self._scaler = StandardScaler()

    def fit(self, X: pd.DataFrame, y=None):
        df = self._add_features(X.copy())
        self._scaler.fit(df[BEHAVIOR_FEATURES + self._extra_cols()])
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = self._add_features(X.copy())
        cols = BEHAVIOR_FEATURES + self._extra_cols()
        present = [c for c in cols if c in df.columns]
        return self._scaler.transform(df[present])

    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Night-time login flag (0-6 or 22-23)
        if "login_hour" in df.columns:
            df["is_night_login"] = df["login_hour"].apply(
                lambda h: 1 if h < 6 or h >= 22 else 0
            )
        # Risk flag combo
        for col in ["is_vpn", "is_tor", "device_change"]:
            if col not in df.columns:
                df[col] = 0
        df["risk_combo"] = df["is_vpn"].astype(int) + df["is_tor"].astype(int) + df["device_change"].astype(int)
        return df

    def _extra_cols(self):
        return ["is_night_login", "risk_combo"]
