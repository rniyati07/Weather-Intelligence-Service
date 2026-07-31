"""Shared fixtures for the API contract tests.

Every dependency that would reach outside the process — database, provider
registry, LLM — is replaced via `app.dependency_overrides`, so this suite
runs fully offline and exercises only the HTTP layer's own behaviour:
routing, auth, validation, serialisation, envelope shape, and error mapping.
"""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.domain.entities.persistence import DailyIntelligenceRecord, Location, RawWeatherReading
from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.entities.weather_intelligence import Narrative, WeatherIntelligence
from app.domain.ports.narration import NarrationPort
from app.domain.ports.provider_registry import (
    FetchResult,
    ProviderHealthEntry,
    ProviderRegistryPort,
)
from app.domain.ports.repository import WeatherRepository
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.config.rule_config_loader import get_rule_config
from app.interface.http import dependencies as deps
from app.main import create_app

API_KEY = "test_consumer_key"
OPS_API_KEY = "test_ops_key"
LOCATION_ID = "15.2993,74.124"

#: Dates are generated relative to today so the horizon validation in
#: `dependencies.validate_date_range` never rejects the fixtures over time.
START = date.today() + timedelta(days=1)
END = START + timedelta(days=2)


def make_reading(day: date, *, stormy: bool) -> NormalizedReading:
    """A storm day (triggers every risk category) or a calm, clear day."""
    if stormy:
        return NormalizedReading(
            date=day,
            temp_min_c=24.0,
            temp_max_c=36.0,
            precipitation_probability=0.9,
            wind_speed_kph=45.0,
            condition=WeatherCondition.THUNDERSTORM,
            completeness=1.0,
            source_class="forecast",
            precipitation_mm=20.0,
            humidity=0.85,
        )
    return NormalizedReading(
        date=day,
        temp_min_c=20.0,
        temp_max_c=27.0,
        precipitation_probability=0.05,
        wind_speed_kph=10.0,
        condition=WeatherCondition.CLEAR,
        completeness=1.0,
        source_class="forecast",
        precipitation_mm=0.0,
        humidity=0.5,
    )


def default_readings() -> list[NormalizedReading]:
    days = [START + timedelta(days=offset) for offset in range((END - START).days + 1)]
    return [make_reading(day, stormy=(index == 0)) for index, day in enumerate(days)]


class FakeRepository(WeatherRepository):
    """In-memory `WeatherRepository`: no database involved."""

    def __init__(self) -> None:
        self.saved_readings: list[RawWeatherReading] = []
        self.saved_intelligence: list[DailyIntelligenceRecord] = []
        self.stored_readings: list[RawWeatherReading] = []

    async def get_or_create_location(
        self, *, name: str, latitude: float, longitude: float, normalized_key: str
    ) -> Location:
        return Location(
            id=1, name=name, latitude=latitude, longitude=longitude, normalized_key=normalized_key
        )

    async def save_raw_reading(self, reading: RawWeatherReading) -> RawWeatherReading:
        self.saved_readings.append(reading)
        return reading

    async def get_raw_readings(
        self, *, location_id: int, start_date: date, end_date: date
    ) -> list[RawWeatherReading]:
        return list(self.stored_readings)

    async def save_intelligence(
        self, record: DailyIntelligenceRecord
    ) -> DailyIntelligenceRecord:
        self.saved_intelligence.append(record)
        return record

    async def get_fresh_intelligence(
        self,
        *,
        location_id: int,
        start_date: date,
        end_date: date,
        rule_config_version: str,
        fresh_since: datetime,
    ) -> list[DailyIntelligenceRecord]:
        return []


class FakeRegistry(ProviderRegistryPort):
    """Scriptable `ProviderRegistryPort`: returns readings, or raises."""

    def __init__(
        self,
        *,
        readings: list[NormalizedReading] | None = None,
        error: Exception | None = None,
        used_fallback: bool = False,
    ) -> None:
        self._readings = readings if readings is not None else default_readings()
        self._error = error
        self._used_fallback = used_fallback

    def select(
        self, data_class: DataClass, *, exclude: set[str] | None = None
    ) -> Iterator[WeatherProvider]:
        return iter(())

    async def fetch_with_fallback(
        self, data_class: DataClass, lat: float, lon: float, start: date, end: date
    ) -> FetchResult:
        if self._error is not None:
            raise self._error
        return FetchResult(readings=self._readings, used_fallback=self._used_fallback)

    def health_snapshot(self) -> list[ProviderHealthEntry]:
        checked = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
        return [
            ProviderHealthEntry(provider="open_meteo", status="available", last_checked_at=checked),
            ProviderHealthEntry(provider="openweather", status="degraded", last_checked_at=checked),
        ]


class FakeNarration(NarrationPort):
    """Scriptable `NarrationPort`: returns a narrative, or raises."""

    def __init__(
        self,
        *,
        text: str = "A stormy start, then clearing.",
        error: Exception | None = None,
    ) -> None:
        self._text = text
        self._error = error

    async def narrate(
        self, intelligence: WeatherIntelligence, language: str = "en"
    ) -> Narrative:
        if self._error is not None:
            raise self._error
        return Narrative(
            generated_by_llm=True,
            summary_text=self._text,
            fallback_used=False,
            model_used="fake-model",
        )


@pytest.fixture
def repository() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def registry() -> FakeRegistry:
    return FakeRegistry()


@pytest.fixture
def narration() -> FakeNarration:
    return FakeNarration()


@pytest.fixture
def app(repository: FakeRepository, registry: FakeRegistry, narration: FakeNarration) -> Any:
    """The real application with only its outbound dependencies overridden."""
    application = create_app()

    async def _session_override() -> AsyncIterator[None]:
        yield None  # the fake repository needs no session

    application.dependency_overrides[deps.get_db_session] = _session_override
    application.dependency_overrides[deps.get_weather_repository] = lambda: repository
    application.dependency_overrides[deps.get_provider_registry_dependency] = lambda: registry
    application.dependency_overrides[deps.get_narration_service_dependency] = lambda: narration

    settings = deps.get_settings()
    application.dependency_overrides[deps.get_app_settings] = lambda: settings.model_copy(
        update={"api_keys": [API_KEY], "ops_api_keys": [OPS_API_KEY]}
    )

    deps.reset_rate_limiter()
    return application


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


@pytest.fixture
def ops_headers() -> dict[str, str]:
    return {"X-API-Key": OPS_API_KEY}


@pytest.fixture
def rule_config_version() -> str:
    return get_rule_config(deps.get_settings().rule_config_version).version


def query() -> dict[str, str]:
    return {"startDate": START.isoformat(), "endDate": END.isoformat()}
