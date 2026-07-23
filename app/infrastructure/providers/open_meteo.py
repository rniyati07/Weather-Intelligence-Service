"""Open-Meteo adapter: the primary forecast provider — no API key required.

Fetches an explicit `[start_date, end_date]` daily forecast (already metric:
°C, km/h — no unit conversion needed) and maps WMO weather codes to
`WeatherCondition`.
"""

from datetime import date
from typing import Any

import httpx

from app.domain.entities.weather import NormalizedReading
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.providers.base import ProviderError, call_with_retry
from app.infrastructure.providers.condition_maps import map_open_meteo_condition
from app.infrastructure.providers.normalization import (
    compute_completeness,
    is_valid_reading,
    percent_to_fraction,
)

_BASE_URL = "https://api.open-meteo.com/v1/forecast"
_DAILY_FIELDS = ",".join(
    [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "precipitation_probability_max",
        "windspeed_10m_max",
        "weathercode",
    ]
)


class OpenMeteoAdapter(WeatherProvider):
    """The primary forecast source: no key, no per-consumer quota friction."""

    name = "open_meteo"
    data_class = DataClass.FORECAST

    def __init__(
        self, client: httpx.AsyncClient, *, retry_attempts: int, retry_backoff_seconds: float
    ) -> None:
        self._client = client
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def is_configured(self) -> bool:
        return True

    async def fetch(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[NormalizedReading]:
        params: dict[str, str | float] = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": _DAILY_FIELDS,
            "timezone": "UTC",
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
        return self._parse(response.json())

    def _parse(self, payload: dict[str, Any]) -> list[NormalizedReading]:
        daily = payload.get("daily")
        if not daily:
            raise ProviderError(self.name, "response missing 'daily' block")

        readings: list[NormalizedReading] = []
        for i, day in enumerate(daily.get("time", [])):
            temp_max_c = float(daily["temperature_2m_max"][i])
            temp_min_c = float(daily["temperature_2m_min"][i])
            precipitation_probability = percent_to_fraction(
                float(daily["precipitation_probability_max"][i])
            )
            wind_speed_kph = float(daily["windspeed_10m_max"][i])
            precipitation_mm = float(daily["precipitation_sum"][i])

            if not is_valid_reading(
                temp_min_c=temp_min_c,
                temp_max_c=temp_max_c,
                precipitation_probability=precipitation_probability,
                wind_speed_kph=wind_speed_kph,
            ):
                continue

            readings.append(
                NormalizedReading(
                    date=date.fromisoformat(day),
                    temp_min_c=temp_min_c,
                    temp_max_c=temp_max_c,
                    precipitation_probability=precipitation_probability,
                    wind_speed_kph=wind_speed_kph,
                    condition=map_open_meteo_condition(int(daily["weathercode"][i])),
                    completeness=compute_completeness(
                        precipitation_mm=precipitation_mm, humidity=None
                    ),
                    source_class="forecast",
                    precipitation_mm=precipitation_mm,
                    humidity=None,
                )
            )
        return readings
