"""OpenWeather adapter: first fallback forecast provider.

The free-tier `/data/2.5/forecast` endpoint returns 3-hourly entries across a
fixed 5-day window (no explicit date-range parameter) — this adapter
aggregates those entries into one `NormalizedReading` per calendar date, per
guide §5.2. Wind arrives in m/s even with `units=metric`, so it still needs
conversion; temperature does not.
"""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.providers.base import ProviderError, call_with_retry
from app.infrastructure.providers.condition_maps import (
    CONDITION_SEVERITY,
    map_openweather_condition,
)
from app.infrastructure.providers.normalization import (
    compute_completeness,
    is_valid_reading,
    mps_to_kph,
    percent_to_fraction,
)

_BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"


class OpenWeatherAdapter(WeatherProvider):
    """First fallback forecast source."""

    name = "openweather"
    data_class = DataClass.FORECAST

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        retry_attempts: int,
        retry_backoff_seconds: float,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def fetch(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[NormalizedReading]:
        params: dict[str, str | float] = {
            "lat": lat,
            "lon": lon,
            "appid": self._api_key,
            "units": "metric",
        }

        async def _request() -> httpx.Response:
            response = await self._client.get(_BASE_URL, params=params)
            response.raise_for_status()
            return response

        response = await call_with_retry(
            _request,
            provider=self.name,
            attempts=self._retry_attempts,
            backoff_seconds=self._retry_backoff_seconds,
        )
        return self._parse(response.json(), start, end)

    def _parse(
        self, payload: dict[str, Any], start: date, end: date
    ) -> list[NormalizedReading]:
        entries = payload.get("list")
        if entries is None:
            raise ProviderError(self.name, "response missing 'list' block")

        by_date: dict[date, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            entry_date = datetime.fromtimestamp(entry["dt"], tz=UTC).date()
            if start <= entry_date <= end:
                by_date[entry_date].append(entry)

        readings: list[NormalizedReading] = []
        for entry_date, day_entries in sorted(by_date.items()):
            reading = self._aggregate_day(entry_date, day_entries)
            if reading is not None:
                readings.append(reading)
        return readings

    def _aggregate_day(
        self, day: date, entries: list[dict[str, Any]]
    ) -> NormalizedReading | None:
        temp_min_c = min(float(e["main"]["temp_min"]) for e in entries)
        temp_max_c = max(float(e["main"]["temp_max"]) for e in entries)
        precipitation_probability = max(float(e.get("pop", 0.0)) for e in entries)
        wind_speed_kph = max(mps_to_kph(float(e["wind"]["speed"])) for e in entries)

        humidity_values = [
            float(e["main"]["humidity"]) for e in entries if "humidity" in e["main"]
        ]
        humidity = (
            percent_to_fraction(sum(humidity_values) / len(humidity_values))
            if humidity_values
            else None
        )

        precipitation_total = 0.0
        has_precip_field = False
        for e in entries:
            rain_mm = e.get("rain", {}).get("3h")
            snow_mm = e.get("snow", {}).get("3h")
            if rain_mm is not None:
                precipitation_total += float(rain_mm)
                has_precip_field = True
            if snow_mm is not None:
                precipitation_total += float(snow_mm)
                has_precip_field = True
        precipitation_mm = precipitation_total if has_precip_field else None

        conditions = [
            map_openweather_condition(int(e["weather"][0]["id"]))
            for e in entries
            if e.get("weather")
        ]
        condition = (
            max(conditions, key=lambda c: CONDITION_SEVERITY[c])
            if conditions
            else WeatherCondition.CLOUDY
        )

        if not is_valid_reading(
            temp_min_c=temp_min_c,
            temp_max_c=temp_max_c,
            precipitation_probability=precipitation_probability,
            wind_speed_kph=wind_speed_kph,
        ):
            return None

        return NormalizedReading(
            date=day,
            temp_min_c=temp_min_c,
            temp_max_c=temp_max_c,
            precipitation_probability=precipitation_probability,
            wind_speed_kph=wind_speed_kph,
            condition=condition,
            completeness=compute_completeness(
                precipitation_mm=precipitation_mm, humidity=humidity
            ),
            source_class="forecast",
            precipitation_mm=precipitation_mm,
            humidity=humidity,
        )
