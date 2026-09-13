"""Error taxonomy and FastAPI exception handlers.

Every failure the app can produce is classified into one of ErrorCategory so
logs and clients can distinguish "your request is malformed" from "a
dependency is down" without parsing free-text messages. User-facing detail
is intentionally short; full context goes to the structured logs only.
"""
from __future__ import annotations

from enum import Enum

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class ErrorCategory(str, Enum):
    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"
    RETRIEVAL_FAILURE = "retrieval_failure"
    MODEL_FAILURE = "model_failure"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    DATABASE_FAILURE = "database_failure"
    ARTIFACT_SANITIZATION_FAILURE = "artifact_sanitization_failure"
    INGESTION_FAILURE = "ingestion_failure"
    INTERNAL = "internal_error"


class AppError(Exception):
    """Base class for application errors with a stable machine-readable category."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    category = ErrorCategory.INTERNAL

    def __init__(self, message: str, *, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    category = ErrorCategory.VALIDATION


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    category = ErrorCategory.NOT_FOUND


class RetrievalError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    category = ErrorCategory.RETRIEVAL_FAILURE


class ModelFailureError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    category = ErrorCategory.MODEL_FAILURE


class ProviderUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    category = ErrorCategory.PROVIDER_UNAVAILABLE


class DatabaseUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    category = ErrorCategory.DATABASE_FAILURE


class ArtifactSanitizationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    category = ErrorCategory.ARTIFACT_SANITIZATION_FAILURE


class IngestionError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    category = ErrorCategory.INGESTION_FAILURE


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "request_failed",
        path=str(request.url.path),
        category=exc.category.value,
        message=exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "category": exc.category.value,
                "message": exc.message,
                "detail": exc.detail,
            }
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=str(request.url.path), error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "category": ErrorCategory.INTERNAL.value,
                "message": "An unexpected error occurred.",
                "detail": None,
            }
        },
    )
