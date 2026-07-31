"""Exception handlers mapping every failure to the API Spec §7 error contract.

One rule governs this module: a client learns the *category* of failure and
nothing else. Stack traces, database detail, and upstream provider identity
never reach a response body (guide §Phase 9 step 6, §5.3).
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.ports.narration import NarrationFailedError
from app.domain.ports.provider_registry import AllProvidersFailedError
from app.interface.http.envelope import error_envelope
from app.interface.http.schemas.common import ErrorCode, ErrorDetailSchema

logger = logging.getLogger(__name__)

_UNKNOWN_REQUEST_ID = "req_unknown"


class ApiError(Exception):
    """Base for failures the HTTP layer raises deliberately, with a fixed contract."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: ErrorCode = "INTERNAL_ERROR"

    def __init__(
        self, message: str, *, details: list[ErrorDetailSchema] | None = None
    ) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class ValidationFailedError(ApiError):
    """400 — malformed or out-of-range parameters (API Spec §11)."""

    status_code = status.HTTP_400_BAD_REQUEST
    code: ErrorCode = "VALIDATION_ERROR"


class AuthenticationFailedError(ApiError):
    """401 — missing or unrecognised `X-API-Key`."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code: ErrorCode = "AUTHENTICATION_ERROR"


class AuthorizationFailedError(ApiError):
    """403 — a valid key that is not permitted for this resource (ops-only routes)."""

    status_code = status.HTTP_403_FORBIDDEN
    code: ErrorCode = "AUTHORIZATION_ERROR"


class RateLimitedError(ApiError):
    """429 — per-key quota exceeded; carries the `Retry-After` hint."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code: ErrorCode = "RATE_LIMITED"

    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message)


def _request_id(request: Request) -> str:
    """The correlation id bound by `RequestContextMiddleware` (Phase 2)."""
    return getattr(request.state, "request_id", _UNKNOWN_REQUEST_ID)


def _json(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    request: Request,
    details: list[ErrorDetailSchema] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    envelope = error_envelope(
        code=code, message=message, request_id=_request_id(request), details=details
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json", by_alias=True),
        headers=headers,
    )


async def handle_api_error(request: Request, exc: Exception) -> JSONResponse:
    """Deliberate HTTP-layer failures already carry their own contract."""
    assert isinstance(exc, ApiError)
    headers = None
    if isinstance(exc, RateLimitedError):
        headers = {"Retry-After": str(exc.retry_after_seconds)}
    return _json(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request=request,
        details=exc.details,
        headers=headers,
    )


async def handle_request_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI/Pydantic body and query validation -> `400 VALIDATION_ERROR`."""
    assert isinstance(exc, RequestValidationError)
    details = [
        ErrorDetailSchema(
            # Drop the leading location kind ("query"/"body") so the field
            # name a client sees matches the name it actually sent.
            field=".".join(str(part) for part in error["loc"][1:]) or str(error["loc"][0]),
            issue=error["msg"],
        )
        for error in exc.errors()
    ]
    return _json(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="VALIDATION_ERROR",
        message="The request failed validation.",
        request=request,
        details=details,
    )


async def handle_all_providers_failed(request: Request, exc: Exception) -> JSONResponse:
    """Every upstream exhausted and no usable stored data -> `503`.

    The message is deliberately generic: it never names a provider.
    """
    logger.warning("all_providers_failed", extra={"error": str(exc)})
    return _json(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="PROVIDER_UNAVAILABLE",
        message="Weather data is temporarily unavailable. Please retry later.",
        request=request,
    )


async def handle_narration_failed(request: Request, exc: Exception) -> JSONResponse:
    """Mandatory narration could not be produced -> `503 SERVICE_DEGRADED`.

    Narration is required in this service (Phase 8 refactor), so a failure is
    a real error rather than a silent templated substitute.
    """
    logger.warning("narration_failed", extra={"error": str(exc)})
    return _json(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        code="SERVICE_DEGRADED",
        message="Narration is temporarily unavailable. Please retry later.",
        request=request,
    )


async def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    """Starlette's own errors (unknown route, 405, ...) into the same envelope."""
    assert isinstance(exc, StarletteHTTPException)
    code: ErrorCode = "NOT_FOUND" if exc.status_code == status.HTTP_404_NOT_FOUND else (
        "AUTHENTICATION_ERROR" if exc.status_code == status.HTTP_401_UNAUTHORIZED
        else "INTERNAL_ERROR" if exc.status_code >= 500
        else "VALIDATION_ERROR"
    )
    return _json(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        request=request,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Anything unhandled -> `500`, logged in full, disclosed generically."""
    logger.exception("unhandled_error")
    return _json(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred. Quote the requestId when reporting this.",
        request=request,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire every handler above onto the application."""
    handlers: dict[Any, Any] = {
        ApiError: handle_api_error,
        RequestValidationError: handle_request_validation_error,
        AllProvidersFailedError: handle_all_providers_failed,
        NarrationFailedError: handle_narration_failed,
        StarletteHTTPException: handle_http_exception,
        Exception: handle_unexpected_error,
    }
    for exception_type, handler in handlers.items():
        app.add_exception_handler(exception_type, handler)
