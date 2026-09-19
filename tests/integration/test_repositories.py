"""Integration tests for `SqlAlchemyWeatherRepository` against a real Postgres.

Uses Testcontainers to spin up an ephemeral `postgres:15-alpine`, matching
the guide's Phase 3 verification bullets: round-trip a reading, round-trip
intelligence, freshness-window filtering, and `rule_config_version`
invalidation. Requires a reachable Docker daemon — the whole module is
skipped (not failed) when one isn't available.

`TEST_DATABASE_URL`, if set, is used directly instead of spinning up a
container — for environments with a real reachable Postgres but no Docker
daemon. Point it at a disposable database: this fixture's teardown runs
`Base.metadata.drop_all`, dropping every table it knows about, every run.
Never point it at a database holding real data.
"""

import os
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.entities.conversation import Conversation
from app.domain.entities.persistence import DailyIntelligenceRecord, RawWeatherReading
from app.domain.entities.trip import GeocodedPlace, TripContext
from app.infrastructure.persistence.models import Base
from app.infrastructure.persistence.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyWeatherRepository,
)

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
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        yield env_url
        return

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


@pytest_asyncio.fixture
async def conversation_repository(session: AsyncSession) -> SqlAlchemyConversationRepository:
    return SqlAlchemyConversationRepository(session)


GOA = GeocodedPlace(name="Goa", latitude=15.2993, longitude=74.1240, country="India")


class TestConversationRoundTrip:
    """Real Postgres round-trip for the JSONB `trip_context` column and the
    messages table — the boundary the date-string bug (stabilization issue 2)
    lived at: a `TripContext` written with real `date` objects must come back
    with real `date` objects, not the strings JSONB stores them as."""

    async def test_create_and_get(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = Conversation.start()

        saved = await conversation_repository.save(conversation)
        fetched = await conversation_repository.get(saved.id)

        assert fetched is not None
        assert fetched.id == conversation.id
        assert fetched.trip_context == TripContext()

    async def test_get_unknown_id_returns_none(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        from uuid import uuid4

        assert await conversation_repository.get(uuid4()) is None

    async def test_trip_context_dates_round_trip_as_real_dates(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        context = TripContext(
            destination=GOA,
            destination_query="Goa",
            start_date=date(2026, 8, 20),
            end_date=date(2026, 8, 23),
            interests=("beach",),
        )
        conversation = Conversation.start().update_context(context)
        await conversation_repository.save(conversation)

        fetched = await conversation_repository.get(conversation.id)

        assert fetched is not None
        assert fetched.trip_context.start_date == date(2026, 8, 20)
        assert isinstance(fetched.trip_context.start_date, date)
        assert fetched.trip_context.end_date == date(2026, 8, 23)
        assert fetched.trip_context.destination == GOA
        assert fetched.trip_context.interests == ("beach",)

    async def test_messages_persist_and_return_in_order(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = Conversation.start()
        conversation = conversation.add_user_message("I want to go to Goa")
        conversation = conversation.add_assistant_message("Great! When are you travelling?")
        await conversation_repository.save(conversation)

        fetched = await conversation_repository.get(conversation.id)

        assert fetched is not None
        assert [m.role for m in fetched.messages] == ["user", "assistant"]
        assert fetched.messages[0].content == "I want to go to Goa"

    async def test_message_metadata_round_trips_through_real_jsonb(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        """The mechanism backend gap 3's clarification flow depends on:
        `Message.metadata` is an opaque dict, and a pending destination
        clarification's candidate list must survive a real Postgres JSONB
        round trip untouched, across a *fresh* repository instance — the
        same "not just an in-memory fake" bar `test_trip_context_dates_round_trip_as_real_dates`
        sets for `TripContext` itself.
        """
        candidates_payload = [
            {
                "name": "Paris",
                "latitude": 48.8566,
                "longitude": 2.3522,
                "country": "France",
                "country_code": "FR",
                "admin1": None,
                "timezone": None,
            },
            {
                "name": "Paris",
                "latitude": 33.6609,
                "longitude": -95.5555,
                "country": "United States",
                "country_code": "US",
                "admin1": "Texas",
                "timezone": None,
            },
        ]
        conversation = Conversation.start()
        conversation = conversation.add_user_message("I'm planning a trip to Paris.")
        conversation = conversation.add_assistant_message(
            'I found more than one location named "Paris". Which one do you mean?',
            metadata={
                "intent": "trip_planning",
                "llm_generated": False,
                "destination_candidates": candidates_payload,
            },
        )
        await conversation_repository.save(conversation)

        # A fresh repository over the same session — not the object that
        # wrote it — proves this is a real read from Postgres, not a
        # returned in-memory reference.
        fresh_repository = SqlAlchemyConversationRepository(conversation_repository._session)
        fetched = await fresh_repository.get(conversation.id)

        assert fetched is not None
        stored_metadata = fetched.messages[-1].metadata
        assert stored_metadata["destination_candidates"] == candidates_payload
        assert stored_metadata["intent"] == "trip_planning"
        assert stored_metadata["llm_generated"] is False

    async def test_update_persists_new_messages_and_context(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = Conversation.start()
        conversation = await conversation_repository.save(conversation)

        conversation = conversation.add_user_message("Goa please")
        conversation = conversation.update_context(TripContext(destination_query="Goa"))
        await conversation_repository.save(conversation)

        fetched = await conversation_repository.get(conversation.id)

        assert fetched is not None
        assert len(fetched.messages) == 1
        assert fetched.trip_context.destination_query == "Goa"

    async def test_get_active_for_user_lists_active_conversations(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        first = await conversation_repository.save(Conversation.start())
        second = await conversation_repository.save(Conversation.start())

        active = await conversation_repository.get_active_for_user()

        active_ids = {c.id for c in active}
        assert first.id in active_ids
        assert second.id in active_ids

    async def test_archived_conversation_excluded_from_active_list(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = await conversation_repository.save(Conversation.start())
        archived = conversation.archive()
        await conversation_repository.save(archived)

        active = await conversation_repository.get_active_for_user()

        assert archived.id not in {c.id for c in active}

    async def test_get_messages_with_limit(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = Conversation.start()
        for i in range(5):
            conversation = conversation.add_user_message(f"message {i}")
        await conversation_repository.save(conversation)

        messages = await conversation_repository.get_messages(conversation.id, limit=2)

        assert len(messages) == 2

    async def test_delete_removes_conversation_and_messages(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        conversation = Conversation.start().add_user_message("hi")
        await conversation_repository.save(conversation)

        deleted = await conversation_repository.delete(conversation.id)

        assert deleted is True
        assert await conversation_repository.get(conversation.id) is None

    async def test_delete_unknown_id_returns_false(
        self, conversation_repository: SqlAlchemyConversationRepository
    ) -> None:
        from uuid import uuid4

        assert await conversation_repository.delete(uuid4()) is False
