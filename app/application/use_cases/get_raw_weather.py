"""`GetRawWeather` — normalized daily readings without intelligence (API Spec §8.4).

Uses the same reading loader as `GetWeatherIntelligence`, so caching,
fallback and persistence behave identically; it simply stops before the
engines run. No provider is identified in the result (guide §5.3).
"""

from dataclasses import dataclass
from datetime import date

from app.application.use_cases.load_readings import WeatherReadingsLoader
from app.domain.entities.weather import NormalizedReading


@dataclass(frozen=True, slots=True)
class RawWeatherResult:
    """Readings for a range, plus the metadata the response envelope needs."""

    readings: list[NormalizedReading]
    cache_status: str
    degraded: bool


class GetRawWeather:
    """Returns provider-agnostic normalized readings for a location and range."""

    def __init__(self, *, loader: WeatherReadingsLoader) -> None:
        self._loader = loader

    async def execute(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> RawWeatherResult:
        loaded = await self._loader.load(
            latitude=latitude, longitude=longitude, start=start, end=end, name=name
        )
        return RawWeatherResult(
            readings=loaded.readings,
            cache_status=loaded.cache_status,
            degraded=loaded.degraded,
        )
