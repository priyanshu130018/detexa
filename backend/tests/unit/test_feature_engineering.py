"""
backend/tests/unit/test_feature_engineering.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for data preprocessing and feature transformations.
"""

import pytest
import pandas as pd
import numpy as np
from app.ml.pipelines.data_preprocessor import BankingDataPreprocessor
from app.ml.pipelines.feature_engineering import BehaviorFeatureEngineer, BankingFeatureEngineer


@pytest.mark.unit
class TestFeatureEngineeringUnit:
    def test_banking_feature_engineer_transform(self):
        eng = BankingFeatureEngineer()
        df = pd.DataFrame([{
            "customer_id": "CUST_1001",
            "account_type": "Savings",
            "transaction_type": "UPI",
            "transaction_amount": 5000.0,
            "transaction_direction": "Debit",
            "account_balance": 25000.0,
            "merchant_category": "Electronics",
            "state": "Maharashtra",
            "credit_score": 720,
            "has_loan": True,
            "loan_type": "Personal",
            "emi_amount": 2500.0,
            "transaction_status": "Completed",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
            "transaction_hour": 14,
            "cust_prior_avg_amount": 3000.0,
            "cust_prior_tx_count": 5.0,
            "amount_to_prior_avg_ratio": 1.66,
        }])
        eng.fit(df)
        transformed = eng.transform(df)
        assert isinstance(transformed, np.ndarray)
        assert transformed.shape[0] == 1

    def test_behavior_feature_engineer_transform(self):
        eng = BehaviorFeatureEngineer()
        df = pd.DataFrame([{
            "login_hour": 3,
            "typing_speed": 2.5,
            "mouse_velocity": 450.0,
            "failed_logins": 4,
            "is_vpn": 1,
            "is_tor": 1,
            "device_change": 1,
        }])
        eng.fit(df)
        transformed = eng.transform(df)
        assert isinstance(transformed, np.ndarray)
        assert transformed.shape[0] == 1

    def test_banking_data_preprocessor_handle_missing(self):
        prep = BankingDataPreprocessor()
        df = pd.DataFrame([{
            "transaction_amount": 500.0,
            "account_balance": 10000.0,
            "credit_score": 700,
            "account_type": "Savings",
            "transaction_type": "UPI",
            "merchant_category": "Grocery",
            "state": "Delhi",
            "channel": "Mobile Banking",
            "kyc_status": "Verified",
        }])
        prep.fit(df)
        transformed = prep.transform(df)
        assert isinstance(transformed, np.ndarray)
        assert transformed.shape[0] == 1
        assert len(prep.get_feature_names()) > 0
