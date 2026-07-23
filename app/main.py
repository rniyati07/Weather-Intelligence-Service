from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.config.settings import get_settings
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.request_context import RequestContextMiddleware
from app.infrastructure.persistence.session import get_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings())
    yield
    await get_database().dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="Weather Intelligence Service", lifespan=lifespan)
    app.add_middleware(RequestContextMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
