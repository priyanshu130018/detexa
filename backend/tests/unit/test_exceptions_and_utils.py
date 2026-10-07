"""
backend/tests/unit/test_exceptions_and_utils.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for custom domain exceptions and logging/utility functions.
"""

import pytest
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    EntityNotFoundException,
    ValidationError,
    ModelInferenceError,
)


@pytest.mark.unit
class TestExceptionsAndUtilsUnit:
    def test_domain_exceptions_messages_and_status(self):
        auth_err = AuthenticationError("Invalid login credentials")
        assert auth_err.status_code == 401
        assert "Invalid login credentials" in auth_err.message

        perm_err = AuthorizationError("Admin rights required")
        assert perm_err.status_code == 403
        assert "Admin rights required" in perm_err.message

        not_found = EntityNotFoundException("Transaction", "tx-999")
        assert not_found.status_code == 404
        assert "Transaction with identifier 'tx-999' not found" in not_found.message

        val_err = ValidationError("Amount must be greater than zero")
        assert val_err.status_code == 400
        assert "Amount must be greater than zero" in val_err.message

        model_err = ModelInferenceError("credit_model", "Matrix dimension mismatch")
        assert model_err.status_code == 502
        assert "credit_model" in model_err.message
