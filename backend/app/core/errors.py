"""Domain errors and exception helpers.

A small set of typed exceptions is mapped to HTTP responses by the API layer so
that services never have to think about HTTP status codes.
"""
from __future__ import annotations


class AppError(Exception):
    """Base application error."""

    status_code = 400
    code = "app_error"

    def __init__(self, message: str, *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class IngestionError(AppError):
    status_code = 422
    code = "ingestion_error"


class DataSourceUnavailable(AppError):
    status_code = 503
    code = "data_source_unavailable"


class LLMUnavailable(AppError):
    status_code = 503
    code = "llm_unavailable"

    def __init__(self, message: str = "The language model service is unavailable.", detail: dict | None = None) -> None:
        super().__init__(message, detail=detail)


class ToolCallError(AppError):
    status_code = 500
    code = "tool_call_error"