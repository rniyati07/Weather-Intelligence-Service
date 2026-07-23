"""OpenWeather adapter: 3-hourly fixture entries aggregated into daily readings."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.domain.entities.weather import WeatherCondition
from app.infrastructure.providers import openweather
from app.infrastructure.providers.openweather import OpenWeatherAdapter

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "providers"
_FIXTURE = json.loads((_FIXTURES_DIR / "openweather_forecast.json").read_text())


@pytest.fixture
def adapter() -> OpenWeatherAdapter:
    return OpenWeatherAdapter(
        httpx.AsyncClient(), api_key="test-key", retry_attempts=2, retry_backoff_seconds=0.01
    )


class TestIsConfigured:
    def test_configured_when_key_present(self, adapter: OpenWeatherAdapter) -> None:
        assert adapter.is_configured() is True

    def test_not_configured_when_key_absent(self) -> None:
        adapter = OpenWeatherAdapter(
            httpx.AsyncClient(), api_key="", retry_attempts=2, retry_backoff_seconds=0.01
        )
        assert adapter.is_configured() is False


class TestFetch:
    @respx.mock
    async def test_sub_daily_entries_aggregate_into_daily_readings(
        self, adapter: OpenWeatherAdapter
    ) -> None:
        respx.get(openweather._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 2
        rainy, clear = readings

        assert rainy.date == date(2026, 8, 1)
        assert rainy.temp_min_c == 24.1
        assert rainy.temp_max_c == 31.2
        assert rainy.precipitation_probability == pytest.approx(0.7)
        assert rainy.wind_speed_kph == pytest.approx(18.36)  # max(3.5,5.1,4.2) m/s -> km/h
        assert rainy.humidity == pytest.approx(0.7666666666666667)
        assert rainy.precipitation_mm == pytest.approx(12.4)
        # worst of {rain(500), heavy_rain(502), rain(501)} by severity -> heavy_rain
        assert rainy.condition == WeatherCondition.HEAVY_RAIN
        assert rainy.completeness == pytest.approx(1.0)

        assert clear.date == date(2026, 8, 2)
        assert clear.temp_min_c == 23.5
        assert clear.temp_max_c == 29.0
        assert clear.wind_speed_kph == pytest.approx(10.08)
        assert clear.humidity == pytest.approx(0.575)
        assert clear.precipitation_mm is None  # no rain/snow field on any entry that day
        assert clear.condition == WeatherCondition.CLEAR
        assert clear.completeness == pytest.approx(0.5)

    @respx.mock
    async def test_entries_outside_requested_range_are_excluded(
        self, adapter: OpenWeatherAdapter
    ) -> None:
        respx.get(openweather._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1))

        assert len(readings) == 1
        assert readings[0].date == date(2026, 8, 1)
