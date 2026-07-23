"""Per-request correlation id: generation, propagation, and ASGI middleware.

`request_id` is bound into every structlog event emitted while a request is
in flight (see `logging.py`) and is surfaced to clients as
`metadata.requestId` (API & Data Contract Specification §9.12).
"""

import secrets
import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"

_logger = structlog.get_logger("app.request")


def generate_request_id() -> str:
    """Return a new correlation id, e.g. `req_9f2c1a7b`."""
    return f"req_{secrets.token_hex(4)}"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Generate a request id per request and bind it (plus path/method) to structlog.

    The id is stored on `request.state.request_id` for use by response
    envelope building (Phase 9) and echoed back as the `X-Request-Id` header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = generate_request_id()
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            _logger.exception("request_failed", duration_ms=duration_ms)
            structlog.contextvars.clear_contextvars()
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        _logger.info("request_handled", status_code=response.status_code, duration_ms=duration_ms)
        structlog.contextvars.clear_contextvars()

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
