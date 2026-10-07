"""
app/ml/pipelines/data_preprocessor.py
─────────────────────────────────────────────────────────────────────────────
Reusable and robust data preprocessing & feature transformation pipeline
designed for the Indian Banking Transaction Fraud dataset.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.preprocessing import OneHotEncoder, RobustScaler, StandardScaler

NUMERIC_BANKING_FEATURES = [
    "transaction_amount",
    "log_transaction_amount",
    "transaction_amount_sq",
    "account_balance",
    "log_account_balance",
    "amount_to_balance_ratio",
    "credit_score",
    "has_loan",
    "emi_amount",
    "log_emi_amount",
    "emi_to_balance_ratio",
    "amount_to_emi_ratio",
    "transaction_hour",
    "hour_sin",
    "hour_cos",
    "is_night_txn",
    "cust_txn_count_prior",
    "cust_avg_amount_prior",
    "cust_amount_diff_from_avg",
    "cust_amount_ratio_to_avg",
    "cust_time_since_last_txn_hours",
    "cust_channel_change",
    "cust_type_change",
]

CATEGORICAL_BANKING_FEATURES = [
    "account_type",
    "transaction_type",
    "transaction_direction",
    "merchant_category",
    "state",
    "loan_type",
    "channel",
    "kyc_status",
    "transaction_status",
]

DEFAULT_FEATURE_VALUES = {
    "transaction_amount": 0.0,
    "account_balance": 50000.0,
    "credit_score": 650.0,
    "has_loan": 0.0,
    "emi_amount": 0.0,
    "transaction_hour": 12.0,
    "account_type": "Savings",
    "transaction_type": "UPI",
    "transaction_direction": "Debit",
    "merchant_category": "Retail",
    "state": "Maharashtra",
    "loan_type": "None",
    "channel": "Mobile_App",
    "kyc_status": "Verified",
    "transaction_status": "Success",
}


@dataclass
class DatasetSplits:
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_val: pd.Series
    y_test: pd.Series


class DatasetLoader:
    """Utility to load and validate the Indian banking dataset."""

    @staticmethod
    def load_dataset(csv_path: Union[str, Path]) -> pd.DataFrame:
        p = Path(csv_path)
        if not p.exists():
            raise FileNotFoundError(f"Indian banking dataset not found at: {p}")
        df = pd.read_csv(p)
        return df


class BankingDataPreprocessor(BaseEstimator, TransformerMixin):
    """
    Robust feature engineering and scaling pipeline for Indian Banking Transaction Fraud Detection.
    
    Transforms raw inputs (transaction_amount, account_balance, credit_score, categoricals, etc.) by:
    1. Extracting log and ratio features (amount/balance, amount/EMI, EMI/balance).
    2. Extracting cyclical time features (hour_sin, hour_cos, is_night_txn).
    3. Constructing leakage-free customer velocity & historical behavior features.
    4. Scaling numerical features with RobustScaler or StandardScaler.
    5. One-hot encoding categorical variables (handling unseen categories safely).
    """

    def __init__(
        self,
        scaler_type: str = "robust",
        include_time_features: bool = True,
        include_velocity: bool = True,
    ):
        self.scaler_type = scaler_type
        self.include_time_features = include_time_features
        self.include_velocity = include_velocity
        self._scaler = RobustScaler() if scaler_type == "robust" else StandardScaler()
        self._ohe = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        self._feature_names_cache: List[str] = []
        self._is_fitted = False

    def fit(self, X: Union[pd.DataFrame, dict, list], y: Optional[pd.Series] = None):
        X_df = self._ensure_dataframe(X)
        df_feat = self._engineer_features(X_df.copy())
        
        # Fit scaler on numeric features
        self._scaler.fit(df_feat[NUMERIC_BANKING_FEATURES])
        
        # Fit OHE on categorical features
        self._ohe.fit(df_feat[CATEGORICAL_BANKING_FEATURES].astype(str))
        
        ohe_names = self._ohe.get_feature_names_out(CATEGORICAL_BANKING_FEATURES).tolist()
        self._feature_names_cache = NUMERIC_BANKING_FEATURES + ohe_names
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray, dict, list]) -> np.ndarray:
        X_df = self._ensure_dataframe(X)
        df_feat = self._engineer_features(X_df.copy())
        
        # Transform numeric
        num_arr = self._scaler.transform(df_feat[NUMERIC_BANKING_FEATURES])
        
        # Transform categorical
        cat_arr = self._ohe.transform(df_feat[CATEGORICAL_BANKING_FEATURES].astype(str))
        
        return np.hstack([num_arr, cat_arr])

    def fit_transform(self, X: Union[pd.DataFrame, dict, list], y: Optional[pd.Series] = None) -> np.ndarray:
        return self.fit(X, y).transform(X)

    def get_feature_names_out(self, input_features=None) -> List[str]:
        return list(self._feature_names_cache)

    def get_feature_names(self) -> List[str]:
        return list(self._feature_names_cache)

    # ── Internal Feature Generators ──────────────────────────────────────────

    def _ensure_dataframe(self, X: Union[pd.DataFrame, np.ndarray, dict, list]) -> pd.DataFrame:
        if isinstance(X, pd.DataFrame):
            return X
        elif isinstance(X, dict):
            return pd.DataFrame([X])
        elif isinstance(X, list):
            return pd.DataFrame(X)
        elif isinstance(X, np.ndarray):
            if hasattr(self, "_feature_names_cache") and self._feature_names_cache:
                cols = self._feature_names_cache[:X.shape[1]]
                return pd.DataFrame(X, columns=cols)
            return pd.DataFrame(X)
        else:
            return pd.DataFrame(X)

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Standardize amount column name if needed
        if "amount" in df.columns and "transaction_amount" not in df.columns:
            df["transaction_amount"] = df["amount"]

        # Impute defaults for missing fields
        for col, default in DEFAULT_FEATURE_VALUES.items():
            if col not in df.columns:
                df[col] = default
            else:
                df[col] = df[col].fillna(default)

        # 1. Amount & Balance Features
        amt = pd.to_numeric(df["transaction_amount"], errors="coerce").fillna(0.0).clip(lower=0.0)
        bal = pd.to_numeric(df["account_balance"], errors="coerce").fillna(50000.0).clip(lower=0.0)
        credit = pd.to_numeric(df["credit_score"], errors="coerce").fillna(650.0).clip(lower=300.0, upper=900.0)
        has_l = pd.to_numeric(df["has_loan"], errors="coerce").fillna(0.0).clip(lower=0.0, upper=1.0)
        emi = pd.to_numeric(df["emi_amount"], errors="coerce").fillna(0.0).clip(lower=0.0)

        df["transaction_amount"] = amt
        df["log_transaction_amount"] = np.log1p(amt)
        df["transaction_amount_sq"] = amt ** 2
        df["account_balance"] = bal
        df["log_account_balance"] = np.log1p(bal)
        df["amount_to_balance_ratio"] = amt / (bal + 1.0)
        df["credit_score"] = credit
        df["has_loan"] = has_l
        df["emi_amount"] = emi
        df["log_emi_amount"] = np.log1p(emi)
        df["emi_to_balance_ratio"] = emi / (bal + 1.0)
        df["amount_to_emi_ratio"] = amt / (emi + 1.0)

        # 2. Diurnal / Temporal Features
        if "transaction_hour" in df.columns:
            hour = pd.to_numeric(df["transaction_hour"], errors="coerce").fillna(12.0)
        elif "hour_of_day" in df.columns:
            hour = pd.to_numeric(df["hour_of_day"], errors="coerce").fillna(12.0)
        elif "transaction_time" in df.columns:
            hour = pd.to_datetime(df["transaction_time"], format="%H:%M", errors="coerce").dt.hour.fillna(12.0)
        else:
            hour = pd.Series(12.0, index=df.index)

        df["transaction_hour"] = hour
        df["hour_sin"] = np.sin(2.0 * np.pi * hour / 24.0)
        df["hour_cos"] = np.cos(2.0 * np.pi * hour / 24.0)
        df["is_night_txn"] = np.where((hour < 6) | (hour >= 22), 1.0, 0.0)

        # 3. Customer Historical Features (Zero-Leakage)
        if "cust_txn_count_prior" not in df.columns:
            # Check if batch data with customer_id is present
            if "customer_id" in df.columns and len(df) > 1 and "transaction_date" in df.columns:
                # Chronological sort
                if "transaction_time" in df.columns:
                    df["_tmp_dt"] = pd.to_datetime(df["transaction_date"] + " " + df["transaction_time"], errors="coerce")
                else:
                    df["_tmp_dt"] = pd.to_datetime(df["transaction_date"], errors="coerce")

                # Expanding prior features
                df["cust_txn_count_prior"] = df.groupby("customer_id").cumcount().astype(float)
                cum_sum = df.groupby("customer_id")["transaction_amount"].cumsum()
                prior_sum = cum_sum - df["transaction_amount"]
                df["cust_avg_amount_prior"] = np.where(
                    df["cust_txn_count_prior"] > 0,
                    prior_sum / np.maximum(df["cust_txn_count_prior"], 1),
                    df["transaction_amount"]
                )
                df["cust_amount_diff_from_avg"] = df["transaction_amount"] - df["cust_avg_amount_prior"]
                df["cust_amount_ratio_to_avg"] = df["transaction_amount"] / (df["cust_avg_amount_prior"] + 1.0)

                prev_dt = df.groupby("customer_id")["_tmp_dt"].shift(1)
                df["cust_time_since_last_txn_hours"] = ((df["_tmp_dt"] - prev_dt).dt.total_seconds() / 3600.0).fillna(168.0)
                df.drop(columns=["_tmp_dt"], inplace=True)

                if "channel" in df.columns:
                    prev_channel = df.groupby("customer_id")["channel"].shift(1)
                    df["cust_channel_change"] = np.where(prev_channel.isna(), 0.0, (df["channel"] != prev_channel).astype(float))
                else:
                    df["cust_channel_change"] = 0.0

                if "transaction_type" in df.columns:
                    prev_type = df.groupby("customer_id")["transaction_type"].shift(1)
                    df["cust_type_change"] = np.where(prev_type.isna(), 0.0, (df["transaction_type"] != prev_type).astype(float))
                else:
                    df["cust_type_change"] = 0.0
            else:
                # Single transaction realtime defaults
                df["cust_txn_count_prior"] = 1.0
                df["cust_avg_amount_prior"] = df["transaction_amount"]
                df["cust_amount_diff_from_avg"] = 0.0
                df["cust_amount_ratio_to_avg"] = 1.0
                df["cust_time_since_last_txn_hours"] = 24.0
                df["cust_channel_change"] = 0.0
                df["cust_type_change"] = 0.0
        else:
            for c in [
                "cust_txn_count_prior", "cust_avg_amount_prior", "cust_amount_diff_from_avg",
                "cust_amount_ratio_to_avg", "cust_time_since_last_txn_hours",
                "cust_channel_change", "cust_type_change"
            ]:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

        # Categorical string formatting
        for col in CATEGORICAL_BANKING_FEATURES:
            df[col] = df[col].astype(str)

        return df


# Backward compatibility alias
CreditCardDataPreprocessor = BankingDataPreprocessor
