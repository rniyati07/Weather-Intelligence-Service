"""Meteostat adapter: historical/baseline provider only.

Never enters the forecast fallback chain (guide §5.2). Temperature and wind
speed arrive already in °C/km/h. Meteostat's daily archive has no coded
weather condition at all — unlike the other three providers, there is no
vocabulary to map. A condition is instead derived from precipitation/snow/
temperature; this is a documented approximation, logged once per fetch, not
a discovered mapping table. Precipitation "probability" is likewise not a
forecast concept for observed data — it is encoded as 1.0/0.0 (it either
rained or it didn't).
"""

import logging
from datetime import date
from typing import Any

import httpx

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.providers.base import ProviderError, call_with_retry
from app.infrastructure.providers.normalization import compute_completeness, is_valid_reading

logger = logging.getLogger(__name__)

_BASE_URL = "https://meteostat.net/point/daily"
_FREEZING_THRESHOLD_C = 2.0


class MeteostatAdapter(WeatherProvider):
    """Historical baseline source — never selected for a forecast request."""

    name = "meteostat"
    data_class = DataClass.HISTORICAL

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
            "start": start.isoformat(),
            "end": end.isoformat(),
        }
        headers = {"X-Api-Key": self._api_key}

        async def _request() -> httpx.Response:
            response = await self._client.get(_BASE_URL, params=params, headers=headers)
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
        records = payload.get("data")
        if records is None:
            raise ProviderError(self.name, "response missing 'data' block")

        if records:
            logger.warning(
                "meteostat_condition_derived",
                extra={
                    "provider": self.name,
                    "reason": "no native condition code; deriving from precipitation/snow/temp",
                    "days": len(records),
                },
            )

        readings: list[NormalizedReading] = []
        for record in records:
            temp_max_c = record.get("tmax")
            temp_min_c = record.get("tmin")
            if temp_max_c is None or temp_min_c is None:
                continue  # unusable day: treated as missing, never fabricated

            temp_max_c = float(temp_max_c)
            temp_min_c = float(temp_min_c)
            precipitation_mm = (
                float(record["prcp"]) if record.get("prcp") is not None else None
            )
            snow_mm = float(record["snow"]) if record.get("snow") is not None else None
            wind_speed_kph = float(record["wspd"]) if record.get("wspd") is not None else 0.0
            # Observed fact, not a forecast: it either rained/snowed or it didn't.
            precipitation_probability = 1.0 if (precipitation_mm or 0.0) > 0.0 else 0.0

            if not is_valid_reading(
                temp_min_c=temp_min_c,
                temp_max_c=temp_max_c,
                precipitation_probability=precipitation_probability,
                wind_speed_kph=wind_speed_kph,
            ):
                continue

            readings.append(
                NormalizedReading(
                    date=date.fromisoformat(record["date"]),
                    temp_min_c=temp_min_c,
                    temp_max_c=temp_max_c,
                    precipitation_probability=precipitation_probability,
                    wind_speed_kph=wind_speed_kph,
                    condition=self._derive_condition(precipitation_mm, snow_mm, temp_max_c),
                    completeness=compute_completeness(
                        precipitation_mm=precipitation_mm, humidity=None
                    ),
                    source_class="historical",
                    precipitation_mm=precipitation_mm,
                    humidity=None,
                )
            )
        return readings

    def _derive_condition(
        self, precipitation_mm: float | None, snow_mm: float | None, temp_max_c: float
    ) -> WeatherCondition:
        if snow_mm and snow_mm > 0.0:
            return WeatherCondition.SNOW
        if precipitation_mm and precipitation_mm > 0.0:
            if temp_max_c <= _FREEZING_THRESHOLD_C:
                return WeatherCondition.SNOW
            return WeatherCondition.RAIN
        return WeatherCondition.CLEAR
