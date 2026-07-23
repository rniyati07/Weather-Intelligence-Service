"""Async SQLAlchemy engine and session management.

The engine is built once from Phase 2's `Settings` and shared for the
process lifetime; sessions are short-lived, one per unit of work. No module
outside this one constructs an engine or session factory directly.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.config.settings import Settings, get_settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the async engine, pooled per Phase 2 settings (`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`)."""
    return create_async_engine(
        str(settings.database_url),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
    )


class Database:
    """Owns the engine and session factory for the process lifetime."""

    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(settings)
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )

    async def dispose(self) -> None:
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session


@lru_cache
def get_database() -> Database:
    """Return the process-wide `Database`, constructed on first call."""
    return Database(get_settings())
