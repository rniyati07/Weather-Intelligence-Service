"""WeatherAPI adapter: fixture payload -> expected `NormalizedReading` (already aggregated)."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.domain.entities.weather import WeatherCondition
from app.infrastructure.providers import weatherapi
from app.infrastructure.providers.weatherapi import WeatherApiAdapter

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "providers" / "weatherapi_forecast.json"
_FIXTURE = json.loads(_FIXTURE_PATH.read_text())


@pytest.fixture
def adapter() -> WeatherApiAdapter:
    return WeatherApiAdapter(
        httpx.AsyncClient(), api_key="test-key", retry_attempts=2, retry_backoff_seconds=0.01
    )


class TestIsConfigured:
    def test_configured_when_key_present(self, adapter: WeatherApiAdapter) -> None:
        assert adapter.is_configured() is True

    def test_not_configured_when_key_absent(self) -> None:
        adapter = WeatherApiAdapter(
            httpx.AsyncClient(), api_key="", retry_attempts=2, retry_backoff_seconds=0.01
        )
        assert adapter.is_configured() is False


class TestFetch:
    @respx.mock
    async def test_fixture_maps_to_expected_readings(self, adapter: WeatherApiAdapter) -> None:
        respx.get(weatherapi._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 2
        rainy, clear = readings

        assert rainy.date == date(2026, 8, 1)
        assert rainy.temp_max_c == 31.0
        assert rainy.temp_min_c == 24.0
        assert rainy.wind_speed_kph == 22.0  # already km/h, no conversion
        assert rainy.precipitation_probability == pytest.approx(0.7)
        assert rainy.humidity == pytest.approx(0.8)
        assert rainy.precipitation_mm == pytest.approx(15.2)
        assert rainy.condition == WeatherCondition.RAIN
        assert rainy.source_class == "forecast"
        assert rainy.completeness == pytest.approx(1.0)

        assert clear.date == date(2026, 8, 2)
        assert clear.condition == WeatherCondition.CLEAR
        assert clear.precipitation_mm == pytest.approx(0.0)  # present (0.0), not missing
        assert clear.completeness == pytest.approx(1.0)

    @respx.mock
    async def test_dates_outside_requested_range_are_excluded(
        self, adapter: WeatherApiAdapter
    ) -> None:
        respx.get(weatherapi._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1))

        assert len(readings) == 1
        assert readings[0].date == date(2026, 8, 1)
