"""
app/core/exceptions.py
─────────────────────────────────────────────────────────────────────────────
Unified domain exception hierarchy and standardized HTTP error handlers.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class ErrorDetail(BaseModel):
    loc: Optional[List[str]] = Field(None, description="Path to invalid field")
    msg: str = Field(..., description="Description of the error")
    type: Optional[str] = Field(None, description="Error type identifier")


class ErrorResponse(BaseModel):
    status_code: int = Field(..., description="HTTP status code")
    error_code: str = Field(..., description="Application error identifier")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Any] = Field(None, description="Granular error details or validation violations")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    path: Optional[str] = Field(None, description="Request path that triggered the error")


# ── Domain Exceptions ────────────────────────────────────────────────────────

class DetexaException(Exception):
    """Base exception for all domain-specific Detexa errors."""
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details


class EntityNotFoundException(DetexaException):
    def __init__(self, entity_name: str, entity_id: Any):
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code=f"{entity_name.upper()}_NOT_FOUND",
        )


class AuthenticationError(DetexaException):
    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_FAILED",
        )


class AuthorizationError(DetexaException):
    def __init__(self, message: str = "Insufficient permissions to perform this action"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="PERMISSION_DENIED",
        )


class ConflictError(DetexaException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="RESOURCE_CONFLICT",
            details=details,
        )


class ModelInferenceError(DetexaException):
    def __init__(self, message: str, model_name: str = "Ensemble"):
        super().__init__(
            message=f"ML inference failure in '{model_name}': {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="MODEL_INFERENCE_FAILED",
        )


class ValidationError(DetexaException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_REQUEST_PARAMETERS",
            details=details,
        )


class DatabaseTransactionError(DetexaException):
    def __init__(self, message: str):
        super().__init__(
            message=f"Database transaction failure: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_TRANSACTION_FAILED",
        )


# ── Exception Registration Handlers ──────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform global exception handlers on the FastAPI application."""

    @app.exception_handler(DetexaException)
    async def detexa_exception_handler(request: Request, exc: DetexaException):
        logger.warning(f"Domain exception [{exc.error_code}] on {request.url.path}: {exc.message}")
        payload = ErrorResponse(
            status_code=exc.status_code,
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            path=request.url.path,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        payload = ErrorResponse(
            status_code=exc.status_code,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            path=request.url.path,
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = [str(x) for x in err.get("loc", [])]
            errors.append(ErrorDetail(loc=loc, msg=err.get("msg", "Invalid value"), type=err.get("type")))

        payload = ErrorResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            message="Request input validation failed. Check 'details' for field violations.",
            details=[e.model_dump() for e in errors],
            path=request.url.path,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Unhandled database error on {request.url.path}: {exc}", exc_info=True)
        payload = ErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            message="An unexpected database error occurred. Transaction was rolled back.",
            path=request.url.path,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled internal server error on {request.url.path}: {exc}", exc_info=True)
        payload = ErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            message="An internal server error occurred.",
            path=request.url.path,
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())
