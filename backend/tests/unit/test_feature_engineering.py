"""
backend/tests/unit/test_feature_engineering.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for data preprocessing and feature transformations.
"""

import pytest
import pandas as pd
import numpy as np
from app.ml.pipelines.data_preprocessor import CreditCardDataPreprocessor
from app.ml.pipelines.feature_engineering import BehaviorFeatureEngineer, CreditFeatureEngineer


@pytest.mark.unit
class TestFeatureEngineeringUnit:
    def test_credit_feature_engineer_transform(self):
        eng = CreditFeatureEngineer()
        df = pd.DataFrame([{
            "Amount": 100.0,
            "V1": 0.5, "V2": -0.2, "V3": 1.2, "V4": -0.8,
            "V14": -0.1, "V17": 0.4
        }])
        eng.fit(df)
        transformed = eng.transform(df)
        assert isinstance(transformed, np.ndarray)
        assert transformed.shape[1] >= 29

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

    def test_credit_card_data_preprocessor_handle_missing(self):
        prep = CreditCardDataPreprocessor(scaler_type="robust")
        df = pd.DataFrame([{"Amount": 50.0, "Time": 1000.0, "V1": 0.2}])
        prep.fit(df)
        transformed = prep.transform(df)
        assert isinstance(transformed, np.ndarray)
        assert transformed.shape[0] == 1
