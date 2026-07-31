"""FastAPI application factory: middleware, routers, exception handlers, lifespan."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.infrastructure.ai.narration_service import get_narration_service
from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.request_context import RequestContextMiddleware
from app.infrastructure.persistence.session import get_database
from app.infrastructure.providers.registry import get_provider_registry
from app.interface.http.errors import register_exception_handlers
from app.interface.http.routers import intelligence, narrative, providers, weather

#: Every documented endpoint lives under this prefix (API Spec §8).
API_V1_PREFIX = "/api/v1"

#: FastAPI declares this by default, but every validation failure is
#: normalised to `400 VALIDATION_ERROR` (API Spec §7.1 defines no 422).
_UNREACHABLE_STATUS = "422"

#: Referenced only by the `422` responses removed above.
_VALIDATION_ONLY_SCHEMAS = ("HTTPValidationError", "ValidationError")

_DESCRIPTION = """
Deterministic weather intelligence with optional AI narration.

Every weather response is **provider-agnostic**: risk levels, activity scores,
packing lists, and rankings are computed by a versioned, deterministic rule
engine, and no upstream provider is ever identified. The AI layer only
restates finished intelligence in natural language — it never computes,
ranks, or alters a value.

All endpoints require an `X-API-Key` header and return the same envelope:
`{ success, data, metadata, error }`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings())
    yield
    await get_database().dispose()
    await get_provider_registry().aclose()
    await get_narration_service().aclose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Weather Intelligence Service",
        description=_DESCRIPTION,
        version="1.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    app.include_router(intelligence.router, prefix=API_V1_PREFIX)
    app.include_router(weather.router, prefix=API_V1_PREFIX)
    app.include_router(narrative.router, prefix=API_V1_PREFIX)
    app.include_router(providers.router, prefix=API_V1_PREFIX)

    @app.get(
        "/health",
        tags=["operations"],
        summary="Liveness probe",
        description="Unauthenticated liveness check. Does not verify downstream dependencies.",
    )
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.openapi = _openapi_matching_runtime(app)  # type: ignore[method-assign]
    return app


def _openapi_matching_runtime(app: FastAPI) -> Callable[[], dict[str, Any]]:
    """Build an `openapi()` that publishes only statuses the service can return.

    FastAPI auto-declares `422` on any route with validated parameters, but
    this service normalises every validation failure to `400 VALIDATION_ERROR`
    in `errors.handle_request_validation_error` — so a documented `422` is
    unreachable. Strip it, along with the validation schemas that only `422`
    referenced, so the published contract matches observed behaviour.

    Documentation only: no request ever reaches this code path.
    """

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        for methods in schema.get("paths", {}).values():
            for operation in methods.values():
                operation.get("responses", {}).pop(_UNREACHABLE_STATUS, None)

        for schema_name in _VALIDATION_ONLY_SCHEMAS:
            schema.get("components", {}).get("schemas", {}).pop(schema_name, None)

        app.openapi_schema = schema
        return schema

    return custom_openapi


app = create_app()
