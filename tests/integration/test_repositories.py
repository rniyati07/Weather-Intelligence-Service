"""Integration tests for `SqlAlchemyWeatherRepository` against a real Postgres.

Uses Testcontainers to spin up an ephemeral `postgres:15-alpine`, matching
the guide's Phase 3 verification bullets: round-trip a reading, round-trip
intelligence, freshness-window filtering, and `rule_config_version`
invalidation. Requires a reachable Docker daemon — the whole module is
skipped (not failed) when one isn't available.
"""

from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities.persistence import DailyIntelligenceRecord, RawWeatherReading
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.repositories import SqlAlchemyWeatherRepository

try:
    from testcontainers.postgres import PostgresContainer
except ImportError:  # pragma: no cover - dev dependency always installed per pyproject
    PostgresContainer = None  # type: ignore[assignment,misc]


def _start_postgres_container() -> "PostgresContainer":
    # `driver=None` yields a bare `postgresql://` URL; we swap in `asyncpg`
    # ourselves rather than adding a sync driver (e.g. psycopg2) purely for
    # test scaffolding when the project is async-only end to end.
    container = PostgresContainer("postgres:15-alpine", driver=None)
    container.start()
    return container


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:  # pragma: no cover - exercised only with Docker
    if PostgresContainer is None:
        pytest.skip("testcontainers is not installed")

    try:
        container = _start_postgres_container()
    except Exception as exc:  # noqa: BLE001 - any Docker-unavailable failure should skip, not fail
        pytest.skip(f"Docker is not available for Testcontainers: {exc}")

    try:
        url = container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://", 1)
        yield url
    finally:
        container.stop()


@pytest_asyncio.fixture
async def session(postgres_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(postgres_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def repository(session: AsyncSession) -> SqlAlchemyWeatherRepository:
    return SqlAlchemyWeatherRepository(session)


@pytest_asyncio.fixture
async def location_id(repository: SqlAlchemyWeatherRepository) -> int:
    location = await repository.get_or_create_location(
        name="Goa", latitude=15.2993, longitude=74.1240, normalized_key="15.2993,74.1240"
    )
    assert location.id is not None
    return location.id


class TestLocationRoundTrip:
    async def test_get_or_create_is_idempotent(
        self, repository: SqlAlchemyWeatherRepository
    ) -> None:
        first = await repository.get_or_create_location(
            name="Goa", latitude=15.2993, longitude=74.1240, normalized_key="15.2993,74.1240"
        )
        second = await repository.get_or_create_location(
            name="Goa (renamed)", latitude=0, longitude=0, normalized_key="15.2993,74.1240"
        )
        assert first.id == second.id
        assert second.name == "Goa"  # existing row wins; no update-on-conflict


class TestReadingRoundTrip:
    async def test_save_and_fetch_reading(
        self, repository: SqlAlchemyWeatherRepository, location_id: int
    ) -> None:
        reading = RawWeatherReading(
            location_id=location_id,
            provider="open_meteo",
            fetched_at=datetime(2026, 8, 1, 6, 0, tzinfo=UTC),
            valid_date=datetime(2026, 8, 1).date(),
            raw_payload={"raw": True},
            normalized_payload={"temp_max_c": 30.0},
        )
        saved = await repository.save_raw_reading(reading)
        assert saved.id is not None

        fetched = await repository.get_raw_readings(
            location_id=location_id,
            start_date=datetime(2026, 8, 1).date(),
            end_date=datetime(2026, 8, 1).date(),
        )
        assert len(fetched) == 1
        assert fetched[0].provider == "open_meteo"
        assert fetched[0].normalized_payload == {"temp_max_c": 30.0}


class TestIntelligenceRoundTripAndFreshness:
    async def test_save_and_fetch_intelligence(
        self, repository: SqlAlchemyWeatherRepository, location_id: int
    ) -> None:
        record = DailyIntelligenceRecord(
            location_id=location_id,
            date=datetime(2026, 8, 1).date(),
            risk_level="high",
            risk_factors=[{"rule": "precip_prob_gt_0_6"}],
            activity_scores={"beach": 20},
            packing=["waterproof jacket"],
            travel_advisory="avoid",
            rule_config_version="2026.07",
            generated_at=datetime.now(UTC),
        )
        saved = await repository.save_intelligence(record)
        assert saved.id is not None

        fetched = await repository.get_fresh_intelligence(
            location_id=location_id,
            start_date=datetime(2026, 8, 1).date(),
            end_date=datetime(2026, 8, 1).date(),
            rule_config_version="2026.07",
            fresh_since=datetime.now(UTC) - timedelta(hours=1),
        )
        assert len(fetched) == 1
        assert fetched[0].risk_level == "high"
        assert fetched[0].travel_advisory == "avoid"

    async def test_stale_rows_are_excluded(
        self, repository: SqlAlchemyWeatherRepository, location_id: int
    ) -> None:
        stale_generated_at = datetime.now(UTC) - timedelta(hours=5)
        record = DailyIntelligenceRecord(
            location_id=location_id,
            date=datetime(2026, 8, 2).date(),
            risk_level="low",
            risk_factors=[],
            activity_scores={"beach": 90},
            packing=["sunscreen"],
            travel_advisory="proceed",
            rule_config_version="2026.07",
            generated_at=stale_generated_at,
        )
        await repository.save_intelligence(record)

        fresh_cutoff = datetime.now(UTC) - timedelta(hours=1)
        fetched = await repository.get_fresh_intelligence(
            location_id=location_id,
            start_date=datetime(2026, 8, 2).date(),
            end_date=datetime(2026, 8, 2).date(),
            rule_config_version="2026.07",
            fresh_since=fresh_cutoff,
        )
        assert fetched == []

    async def test_rule_config_version_change_excludes_prior_rows(
        self, repository: SqlAlchemyWeatherRepository, location_id: int
    ) -> None:
        record = DailyIntelligenceRecord(
            location_id=location_id,
            date=datetime(2026, 8, 3).date(),
            risk_level="moderate",
            risk_factors=[],
            activity_scores={"beach": 60},
            packing=[],
            travel_advisory="caution",
            rule_config_version="2026.07",
            generated_at=datetime.now(UTC),
        )
        await repository.save_intelligence(record)

        fetched = await repository.get_fresh_intelligence(
            location_id=location_id,
            start_date=datetime(2026, 8, 3).date(),
            end_date=datetime(2026, 8, 3).date(),
            rule_config_version="2026.08",  # bumped version excludes the prior row
            fresh_since=datetime.now(UTC) - timedelta(hours=1),
        )
        assert fetched == []
