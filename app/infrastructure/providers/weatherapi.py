"""WeatherAPI adapter: second fallback forecast provider.

`/forecast.json` returns already daily-aggregated fields, already metric
(`maxtemp_c`, `maxwind_kph`) — no conversion needed. The endpoint takes a
`days` count rather than an explicit range, so `days` is derived from the
requested window and clamped to what the API supports; any requested date
the response doesn't cover is simply absent from the result.
"""

from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.domain.entities.weather import NormalizedReading
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.providers.base import ProviderError, call_with_retry
from app.infrastructure.providers.condition_maps import map_weatherapi_condition
from app.infrastructure.providers.normalization import (
    compute_completeness,
    is_valid_reading,
    percent_to_fraction,
)

_BASE_URL = "http://api.weatherapi.com/v1/forecast.json"
_MAX_DAYS = 14


class WeatherApiAdapter(WeatherProvider):
    """Second fallback forecast source."""

    name = "weatherapi"
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
        today = datetime.now(UTC).date()
        days = min(_MAX_DAYS, max(1, (end - today).days + 1))
        params: dict[str, str | int] = {
            "key": self._api_key,
            "q": f"{lat},{lon}",
            "days": days,
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
        forecast_days = payload.get("forecast", {}).get("forecastday")
        if forecast_days is None:
            raise ProviderError(self.name, "response missing 'forecast.forecastday' block")

        readings: list[NormalizedReading] = []
        for entry in forecast_days:
            entry_date = date.fromisoformat(entry["date"])
            if not (start <= entry_date <= end):
                continue

            day = entry["day"]
            temp_max_c = float(day["maxtemp_c"])
            temp_min_c = float(day["mintemp_c"])
            precipitation_probability = percent_to_fraction(
                float(day.get("daily_chance_of_rain", 0))
            )
            wind_speed_kph = float(day["maxwind_kph"])
            precipitation_mm = float(day["totalprecip_mm"])
            humidity = (
                percent_to_fraction(float(day["avghumidity"]))
                if "avghumidity" in day
                else None
            )

            if not is_valid_reading(
                temp_min_c=temp_min_c,
                temp_max_c=temp_max_c,
                precipitation_probability=precipitation_probability,
                wind_speed_kph=wind_speed_kph,
            ):
                continue

            readings.append(
                NormalizedReading(
                    date=entry_date,
                    temp_min_c=temp_min_c,
                    temp_max_c=temp_max_c,
                    precipitation_probability=precipitation_probability,
                    wind_speed_kph=wind_speed_kph,
                    condition=map_weatherapi_condition(int(day["condition"]["code"])),
                    completeness=compute_completeness(
                        precipitation_mm=precipitation_mm, humidity=humidity
                    ),
                    source_class="forecast",
                    precipitation_mm=precipitation_mm,
                    humidity=humidity,
                )
            )
        return readings
