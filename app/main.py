"""FastAPI application factory: middleware, routers, exception handlers, lifespan."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

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

    return app


app = create_app()
