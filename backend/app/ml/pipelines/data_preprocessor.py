"""
app/ml/pipelines/data_preprocessor.py
─────────────────────────────────────────────────────────────────────────────
Reusable and robust data preprocessing & feature transformation pipeline
designed for the Kaggle Credit Card Fraud dataset.
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import RobustScaler, StandardScaler


@dataclass
class DatasetSplits:
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series


class CreditCardDataPreprocessor(BaseEstimator, TransformerMixin):
    """
    Robust feature engineering and scaling pipeline for Credit Card Fraud Detection.
    
    Transforms raw inputs (Time, Amount, V1-V28) by:
    1. Extracting cyclical time features (hour of day, sin/cos transformations).
    2. Applying log1p transformation to monetary Amount to compress heavy right-tail.
    3. Constructing non-linear PCA interaction terms for top correlated components.
    4. Computing composite L2 norm across orthogonal components.
    5. Scaling numerical features with RobustScaler (median & IQR centering).
    """

    def __init__(
        self,
        scaler_type: str = "robust",
        include_time_features: bool = True,
        include_interactions: bool = True,
    ):
        self.scaler_type = scaler_type
        self.include_time_features = include_time_features
        self.include_interactions = include_interactions
        self._scaler = RobustScaler() if scaler_type == "robust" else StandardScaler()
        self._feature_names_cache: List[str] = []

    def fit(self, X: pd.DataFrame, y: Optional[pd.Series] = None):
        X_df = self._ensure_dataframe(X)
        df_feat = self._engineer_features(X_df.copy())
        cols = self._get_engineered_column_names(df_feat)
        self._feature_names_cache = cols
        self._scaler.fit(df_feat[cols])
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray:
        X_df = self._ensure_dataframe(X)
        df_feat = self._engineer_features(X_df.copy())
        cols = self._feature_names_cache or self._get_engineered_column_names(df_feat)
        return self._scaler.transform(df_feat[cols])

    def fit_transform(self, X: pd.DataFrame, y: Optional[pd.Series] = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def get_feature_names_out(self, input_features=None) -> List[str]:
        return list(self._feature_names_cache)

    # ── Internal Feature Generators ──────────────────────────────────────────

    def _ensure_dataframe(self, X: Union[pd.DataFrame, np.ndarray, dict]) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            return X
        elif isinstance(X, dict):
            return pd.DataFrame([X])
        elif isinstance(X, np.ndarray):
            cols = [f"V{i}" for i in range(1, 29)] + ["Amount"]
            if X.shape[1] == len(cols) + 1:
                cols = ["Time"] + cols
            return pd.DataFrame(X, columns=cols[:X.shape[1]])
        else:
            return pd.DataFrame(X)

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Standardize column casing
        col_map = {c: c.capitalize() if c.lower().startswith("v") else c for c in df.columns}
        if "amount" in col_map:
            col_map["amount"] = "Amount"
        if "time" in col_map:
            col_map["time"] = "Time"
        df.rename(columns=col_map, inplace=True)

        # 1. Amount Features
        if "Amount" in df.columns:
            amount_clean = df["Amount"].clip(lower=0.0)
            df["log_amount"] = np.log1p(amount_clean)
            df["amount_sq"] = amount_clean ** 2
        else:
            df["Amount"] = 0.0
            df["log_amount"] = 0.0
            df["amount_sq"] = 0.0

        # 2. Time Features
        if self.include_time_features:
            if "Time" in df.columns:
                hour_of_day = (df["Time"] % 86400) / 3600.0
            elif "hour_of_day" in df.columns:
                hour_of_day = df["hour_of_day"]
            else:
                hour_of_day = pd.Series([12.0] * len(df), index=df.index)

            df["hour_of_day"] = hour_of_day
            df["sin_time"] = np.sin(2 * np.pi * hour_of_day / 24.0)
            df["cos_time"] = np.cos(2 * np.pi * hour_of_day / 24.0)
            df["is_night_txn"] = ((hour_of_day < 6) | (hour_of_day >= 22)).astype(float)


        # Ensure all 28 PCA features exist
        for i in range(1, 29):
            col = f"V{i}"
            if col not in df.columns:
                df[col] = 0.0

        # 3. Non-Linear Interaction Features
        if self.include_interactions:
            # Strongest correlated pairs identified from EDA
            interactions = [
                ("V14", "V17"),
                ("V12", "V10"),
                ("V14", "V12"),
                ("V17", "V12"),
                ("V4", "V11"),
                ("V1", "V2"),
                ("V3", "V7"),
            ]
            for a, b in interactions:
                if a in df.columns and b in df.columns:
                    df[f"{a}_{b}_interaction"] = df[a] * df[b]

            # Orthogonal component norm
            v_cols = [f"V{i}" for i in range(1, 29)]
            df["v_norm"] = np.sqrt((df[v_cols] ** 2).sum(axis=1))

        return df

    def _get_engineered_column_names(self, df: pd.DataFrame) -> List[str]:
        # Exclude target and raw timestamp
        exclude = {"Class", "class", "target", "Time"}
        return [c for c in df.columns if c not in exclude]


class DatasetLoader:
    """Helper utility to load, inspect, clean, and stratify the credit card dataset."""

    @staticmethod
    def load_csv(csv_path: str, drop_duplicates: bool = False) -> Tuple[pd.DataFrame, pd.Series]:
        df = pd.read_csv(csv_path)
        if drop_duplicates:
            df = df.drop_duplicates().reset_index(drop=True)
        
        X = df.drop(columns=["Class"])
        y = df["Class"]
        return X, y

    @staticmethod
    def create_stratified_splits(
        X: pd.DataFrame,
        y: pd.Series,
        val_size: float = 0.15,
        test_size: float = 0.15,
        random_state: int = 42,
    ) -> DatasetSplits:
        """
        Produce train, validation, and test splits with preserved fraud class ratio
        and zero test data leakage.
        """
        # Step 1: Split off Test set
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            X, y, test_size=test_size, stratify=y, random_state=random_state
        )

        # Step 2: Split Train and Validation
        val_ratio_adjusted = val_size / (1.0 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=val_ratio_adjusted, stratify=y_train_val, random_state=random_state
        )

        return DatasetSplits(
            X_train=X_train.reset_index(drop=True),
            X_val=X_val.reset_index(drop=True),
            X_test=X_test.reset_index(drop=True),
            y_train=y_train.reset_index(drop=True),
            y_val=y_val.reset_index(drop=True),
            y_test=y_test.reset_index(drop=True),
        )

    @staticmethod
    def get_stratified_kfold(n_splits: int = 5, random_state: int = 42) -> StratifiedKFold:
        return StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
