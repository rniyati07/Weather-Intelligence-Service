"""Shared FastAPI dependencies: settings, DB session, and repository injection.

Application code receives configuration and infrastructure through these
dependencies rather than importing their concrete modules directly, so
routes and use cases stay decoupled from *how* things are constructed and
remain overridable in tests via `app.dependency_overrides`.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.repository import WeatherRepository
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.persistence.repositories import SqlAlchemyWeatherRepository
from app.infrastructure.persistence.session import get_database


def get_app_settings() -> Settings:
    """FastAPI dependency returning the process-wide, cached `Settings`."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """One session per request: commits on success, rolls back on exception."""
    async with get_database().session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_weather_repository(session: DbSessionDep) -> WeatherRepository:
    """FastAPI dependency returning a `WeatherRepository` bound to the request's session."""
    return SqlAlchemyWeatherRepository(session)


WeatherRepositoryDep = Annotated[WeatherRepository, Depends(get_weather_repository)]
