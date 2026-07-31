"""Shared reading acquisition: resolve the location, then serve or fetch readings.

Both `GetWeatherIntelligence` and `GetRawWeather` need exactly the same
"read store -> on miss/stale fetch via the registry -> persist" sequence
(guide §Phase 9 step 5), so it lives here once rather than being duplicated
in each use case.

Depends only on domain ports; concrete adapters are injected at the HTTP
boundary (guide §3.1).
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.application.dto.weather_reading import reading_from_payload, reading_to_payload
from app.domain.entities.persistence import RawWeatherReading
from app.domain.entities.weather import NormalizedReading
from app.domain.ports.provider_registry import AllProvidersFailedError, ProviderRegistryPort
from app.domain.ports.repository import WeatherRepository
from app.domain.ports.weather_provider import DataClass

#: `metadata.cacheStatus` values (API Spec §10 `CacheStatus`).
CACHE_HIT = "hit"
CACHE_MISS = "miss"
CACHE_STALE = "stale"

#: Provider recorded on rows this service persists. Provider identity is not
#: threaded out of the registry (guide §5.3), so stored rows carry the
#: service-level origin rather than a specific upstream name.
_PERSISTED_PROVIDER = "registry"


@dataclass(frozen=True, slots=True)
class LoadedReadings:
    """Readings for a range, plus where they came from."""

    location_id: int
    readings: list[NormalizedReading]
    cache_status: str
    degraded: bool


class WeatherReadingsLoader:
    """Resolves a location and returns readings, fetching only when needed."""

    def __init__(
        self,
        *,
        repository: WeatherRepository,
        registry: ProviderRegistryPort,
        provider_cache_ttl_seconds: int,
    ) -> None:
        self._repository = repository
        self._registry = registry
        self._provider_cache_ttl_seconds = provider_cache_ttl_seconds

    async def load(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> LoadedReadings:
        normalized_key = f"{latitude},{longitude}"
        location = await self._repository.get_or_create_location(
            name=name or normalized_key,
            latitude=latitude,
            longitude=longitude,
            normalized_key=normalized_key,
        )
        if location.id is None:  # pragma: no cover - repository always assigns an id
            raise RuntimeError("repository returned a location without an id")

        stored = await self._repository.get_raw_readings(
            location_id=location.id, start_date=start, end_date=end
        )
        cutoff = datetime.now(UTC) - timedelta(seconds=self._provider_cache_ttl_seconds)
        fresh = [row for row in stored if row.fetched_at >= cutoff]
        expected_days = (end - start).days + 1

        if len({row.valid_date for row in fresh}) == expected_days:
            return LoadedReadings(location.id, self._latest_per_day(fresh), CACHE_HIT, False)

        try:
            result = await self._registry.fetch_with_fallback(
                DataClass.FORECAST, latitude, longitude, start, end
            )
        except AllProvidersFailedError:
            # Stale-serve beats a 503 when usable stored data exists (guide
            # §5.3). With nothing stored, the error propagates to a 503.
            if not stored:
                raise
            return LoadedReadings(location.id, self._latest_per_day(stored), CACHE_STALE, True)

        await self._persist_readings(location.id, result.readings)
        return LoadedReadings(location.id, result.readings, CACHE_MISS, result.used_fallback)

    @staticmethod
    def _latest_per_day(rows: list[RawWeatherReading]) -> list[NormalizedReading]:
        """Collapse stored rows to one reading per date, newest fetch winning."""
        newest: dict[date, RawWeatherReading] = {}
        for row in rows:
            current = newest.get(row.valid_date)
            if current is None or row.fetched_at > current.fetched_at:
                newest[row.valid_date] = row
        return [reading_from_payload(newest[day].normalized_payload) for day in sorted(newest)]

    async def _persist_readings(
        self, location_id: int, readings: list[NormalizedReading]
    ) -> None:
        fetched_at = datetime.now(UTC)
        for reading in readings:
            payload = reading_to_payload(reading)
            await self._repository.save_raw_reading(
                RawWeatherReading(
                    location_id=location_id,
                    provider=_PERSISTED_PROVIDER,
                    fetched_at=fetched_at,
                    valid_date=reading.date,
                    raw_payload=payload,
                    normalized_payload=payload,
                )
            )
