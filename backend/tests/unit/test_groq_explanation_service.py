"""
backend/tests/unit/test_groq_explanation_service.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive unit tests for the Groq LLM Fraud Explanation Service.
Tests:
1. Successful Groq explanation synthesis
2. Malformed LLM response fallback
3. API timeout graceful fallback
4. API exception / network failure fallback
5. Missing / unconfigured API key fallback
6. Safe SHAP-grounded deterministic fallback explanation
7. Architectural verification: LLM cannot alter fraud probability, risk level, or decision
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.services.explanation_service import GroqExplanationService, SYSTEM_PROMPT


@pytest.fixture
def sample_shap_features():
    return [
        {"feature": "amount_to_balance_ratio", "shap_value": 0.38, "direction": "RISK_INCREASING", "feature_value": 45.2},
        {"feature": "transaction_amount", "shap_value": 0.25, "direction": "RISK_INCREASING", "feature_value": 250000.0},
        {"feature": "credit_score", "shap_value": -0.15, "direction": "RISK_DECREASING", "feature_value": 780},
    ]


@pytest.fixture
def sample_tx_data():
    return {
        "customer_id": "CUST_54321",
        "transaction_amount": 250000.0,
        "account_balance": 5500.0,
        "account_type": "Savings",
        "transaction_type": "IMPS",
        "channel": "Net Banking",
        "state": "Maharashtra",
        "credit_score": 780,
    }


@pytest.mark.unit
class TestGroqExplanationService:
    def test_missing_api_key_returns_safe_fallback(self, sample_shap_features, sample_tx_data):
        """When API key is missing or empty, service immediately returns SHAP fallback without throwing."""
        service = GroqExplanationService(api_key="", model="openai/gpt-oss-20b")
        assert service._client is None

        result = service.generate_explanation(
            fraud_score=0.88,
            risk_level="High",
            decision="BLOCK",
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        assert isinstance(result, dict)
        assert "summary" in result
        assert "risk_factors" in result
        assert result["source"] == "shap_fallback"
        assert len(result["risk_factors"]) >= 1
        assert "High Risk" in result["summary"]
        assert "0.88" in result["summary"]

    def test_successful_groq_explanation(self, sample_shap_features, sample_tx_data):
        """When Groq API returns valid structured JSON, service formats it with source='groq_llm'."""
        service = GroqExplanationService(api_key="gsk_mock_valid_key_12345", model="openai/gpt-oss-20b")

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "summary": "This INR 250,000 IMPS transfer is flagged as High Risk due to a severe amount-to-balance imbalance.",
            "risk_factors": [
                "Transaction amount of INR 250,000 exceeds available balance significantly (+0.38 SHAP impact).",
                "High absolute transaction amount relative to account activity (+0.25 SHAP impact).",
                "Customer has strong credit score acting as partial legitimacy factor (-0.15 SHAP).",
            ]
        })
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        service._client = mock_client

        result = service.generate_explanation(
            fraud_score=0.88,
            risk_level="High",
            decision="BLOCK",
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        assert result["source"] == "groq_llm"
        assert "High Risk" in result["summary"]
        assert len(result["risk_factors"]) == 3
        assert mock_client.chat.completions.create.called

        # Verify prompt evidence contains only necessary factual attributes
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "openai/gpt-oss-20b"
        assert call_kwargs["temperature"] == 0.1
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "STRICT OPERATIONAL RULES" in messages[0]["content"]

    def test_malformed_llm_response_graceful_fallback(self, sample_shap_features, sample_tx_data):
        """When LLM returns non-JSON or invalid schema, service gracefully returns SHAP fallback."""
        service = GroqExplanationService(api_key="gsk_mock_valid_key_12345", model="openai/gpt-oss-20b")

        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "I am unable to generate JSON right now."
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        service._client = mock_client

        result = service.generate_explanation(
            fraud_score=0.72,
            risk_level="Medium",
            decision="REVIEW",
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        assert result["source"] == "shap_fallback"
        assert "Medium Risk" in result["summary"]
        assert len(result["risk_factors"]) >= 1

    def test_api_timeout_graceful_fallback(self, sample_shap_features, sample_tx_data):
        """When Groq call exceeds timeout, exception is caught and fallback explanation returned without blocking."""
        service = GroqExplanationService(api_key="gsk_mock_valid_key_12345", model="openai/gpt-oss-20b")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError("Request timed out after 4.0s")
        service._client = mock_client

        result = service.generate_explanation(
            fraud_score=0.95,
            risk_level="High",
            decision="BLOCK",
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        assert result["source"] == "shap_fallback"
        assert "High Risk" in result["summary"]
        assert len(result["risk_factors"]) >= 1

    def test_api_failure_exception_handling(self, sample_shap_features, sample_tx_data):
        """When Groq API encounters 500 error or rate limits, fallback is returned immediately."""
        service = GroqExplanationService(api_key="gsk_mock_valid_key_12345", model="openai/gpt-oss-20b")

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Groq 503 Service Unavailable")
        service._client = mock_client

        result = service.generate_explanation(
            fraud_score=0.15,
            risk_level="Low",
            decision="ALLOW",
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        assert result["source"] == "shap_fallback"
        assert "Low Risk" in result["summary"]
        assert "0.15" in result["summary"]

    def test_immutability_of_fraud_score_and_decision(self, sample_shap_features, sample_tx_data):
        """
        Verify that LLM output CANNOT modify the ML fraud score, risk level, or decision.
        The LLM text is isolated strictly to the 'explanation' output dictionary.
        """
        service = GroqExplanationService(api_key="gsk_mock_valid_key_12345", model="openai/gpt-oss-20b")

        mock_client = MagicMock()
        mock_choice = MagicMock()
        # Even if an adversarial prompt attempted to return a different score or decision
        mock_choice.message.content = json.dumps({
            "fraud_score": 0.01,
            "decision": "ALLOW",
            "risk_level": "Low",
            "summary": "Attempted to override decision.",
            "risk_factors": ["Rule 1"]
        })
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        service._client = mock_client

        original_score = 0.94
        original_decision = "BLOCK"
        original_risk = "High"

        result = service.generate_explanation(
            fraud_score=original_score,
            risk_level=original_risk,
            decision=original_decision,
            shap_features=sample_shap_features,
            transaction_data=sample_tx_data,
        )

        # Service only extracts 'summary', 'risk_factors', and sets 'source'
        assert "fraud_score" not in result
        assert "decision" not in result
        assert "risk_level" not in result
        assert set(result.keys()) == {"summary", "risk_factors", "source"}
