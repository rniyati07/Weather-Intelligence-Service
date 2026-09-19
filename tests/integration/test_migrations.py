"""Alembic migration `0002` — upgrade/downgrade against a real Postgres.

Requires a reachable Docker daemon — skipped, not failed, when one isn't
available, matching `test_repositories.py`'s convention. `env.py` sources its
URL from `Settings` (never a hardcoded `alembic.ini` URL), so this test
points at the ephemeral container by setting `DATABASE_URL` and clearing the
settings cache before invoking Alembic.

`command.upgrade`/`command.downgrade` are synchronous and `env.py` itself
calls `asyncio.run(...)` internally — calling either directly from this
`async def` test would raise "asyncio.run() cannot be called from a running
event loop". Run through `asyncio.to_thread` instead, where no loop is
already running.

`TEST_DATABASE_URL`, if set, is used directly instead of a container — same
escape hatch as `test_repositories.py`, same warning: point it at a
disposable database, this module repeatedly creates and drops every table
Alembic knows about. Accepts either a bare `postgresql://` or a
`+asyncpg`-suffixed URL; the driver suffix is stripped where this file needs
a sync engine.
"""

import asyncio
import os
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.config.settings import get_settings

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:  # pragma: no cover - dev dependency always installed per pyproject
    PostgresContainer = None  # type: ignore[assignment,misc]

_REQUIRED_NON_DB_ENV = {
    "API_KEYS": "dev_key_local",
    "LLM_API_KEY": "test-llm-key",
    "LLM_MODEL": "test-model",
    "LLM_BASE_URL": "https://api.example-llm.test/v1",
}

_EXPECTED_TABLES = {
    "locations",
    "providers",
    "weather_readings_raw",
    "weather_intelligence_daily",
    "conversations",
    "messages",
}


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:  # pragma: no cover - exercised only with Docker
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        yield env_url.replace("+asyncpg", "", 1)
        return

    if PostgresContainer is None:
        pytest.skip("testcontainers is not installed")
    try:
        container = PostgresContainer("postgres:15-alpine", driver=None)
        container.start()
    except Exception as exc:  # noqa: BLE001 - any Docker-unavailable failure should skip, not fail
        pytest.skip(f"Docker is not available for Testcontainers: {exc}")

    try:
        yield container.get_connection_url()  # sync `postgresql://` — fine for Alembic + inspection
    finally:
        container.stop()


@pytest.fixture
def alembic_config(monkeypatch: pytest.MonkeyPatch, postgres_url: str) -> Config:
    async_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    monkeypatch.setenv("DATABASE_URL", async_url)
    for key, value in _REQUIRED_NON_DB_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    config = Config("alembic.ini")
    yield config

    get_settings.cache_clear()


async def _table_names(url: str) -> set[str]:
    """Introspect via the async engine — this project has no sync driver
    installed (`asyncpg` only, deliberately, per `test_repositories.py`'s own
    comment), so a plain `create_engine`/`sa.inspect` here would require
    adding one just for this one helper. `run_sync` bridges SQLAlchemy's
    (inherently synchronous) inspection API onto the async connection
    instead — no new dependency, same async-only architecture everywhere
    else in this codebase.
    """
    async_url = (
        url if "+asyncpg" in url else url.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    engine = create_async_engine(async_url)

    def _inspect(sync_conn: sa.Connection) -> set[str]:
        return set(sa.inspect(sync_conn).get_table_names())

    try:
        async with engine.connect() as conn:
            return await conn.run_sync(_inspect)
    finally:
        await engine.dispose()


class TestMigrationUpgradeDowngrade:
    async def test_upgrade_head_creates_every_table(
        self, alembic_config: Config, postgres_url: str
    ) -> None:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        tables = await _table_names(postgres_url)

        assert tables >= _EXPECTED_TABLES

        await asyncio.to_thread(command.downgrade, alembic_config, "base")

    async def test_downgrade_base_drops_every_table(
        self, alembic_config: Config, postgres_url: str
    ) -> None:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        await asyncio.to_thread(command.downgrade, alembic_config, "base")

        tables = await _table_names(postgres_url)
        assert _EXPECTED_TABLES.isdisjoint(tables)

    async def test_downgrade_to_0001_keeps_weather_tables_drops_conversation_tables(
        self, alembic_config: Config, postgres_url: str
    ) -> None:
        """`0002` must be independently reversible without touching `0001`'s tables."""
        await asyncio.to_thread(command.upgrade, alembic_config, "head")

        await asyncio.to_thread(command.downgrade, alembic_config, "0001")

        tables = await _table_names(postgres_url)
        weather_tables = {
            "locations", "providers", "weather_readings_raw", "weather_intelligence_daily"
        }
        assert weather_tables <= tables
        assert {"conversations", "messages"}.isdisjoint(tables)

        await asyncio.to_thread(command.downgrade, alembic_config, "base")
