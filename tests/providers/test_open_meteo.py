"""Open-Meteo adapter: fixture payload -> expected `NormalizedReading`, offline via respx."""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.domain.entities.weather import WeatherCondition
from app.infrastructure.providers import open_meteo
from app.infrastructure.providers.open_meteo import OpenMeteoAdapter

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "providers" / "open_meteo_forecast.json"
_FIXTURE = json.loads(_FIXTURE_PATH.read_text())


@pytest.fixture
def adapter() -> OpenMeteoAdapter:
    return OpenMeteoAdapter(httpx.AsyncClient(), retry_attempts=2, retry_backoff_seconds=0.01)


class TestIsConfigured:
    def test_always_configured(self, adapter: OpenMeteoAdapter) -> None:
        assert adapter.is_configured() is True


class TestFetch:
    @respx.mock
    async def test_fixture_maps_to_expected_readings(self, adapter: OpenMeteoAdapter) -> None:
        respx.get(open_meteo._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 2
        rainy, clear = readings

        assert rainy.date == date(2026, 8, 1)
        assert rainy.temp_max_c == 31.2
        assert rainy.temp_min_c == 24.1
        assert rainy.precipitation_probability == pytest.approx(0.7)
        assert rainy.wind_speed_kph == 18.3
        assert rainy.precipitation_mm == 12.4
        assert rainy.condition == WeatherCondition.RAIN
        assert rainy.source_class == "forecast"
        assert rainy.humidity is None
        assert rainy.completeness == pytest.approx(0.5)  # precipitation_mm present, humidity absent

        assert clear.date == date(2026, 8, 2)
        assert clear.condition == WeatherCondition.CLEAR
        assert clear.precipitation_probability == pytest.approx(0.05)

    @respx.mock
    async def test_new_real_fields_are_parsed_and_humidity_is_populated(
        self, adapter: OpenMeteoAdapter
    ) -> None:
        """Live-verified against the real Open-Meteo API: these fields are
        genuinely available, free, keyless, alongside the ones already
        fetched — `humidity` had been hardcoded `None` for every Open-Meteo
        reading despite `relative_humidity_2m_max` being real, fetchable
        data the whole time."""
        enriched = json.loads(json.dumps(_FIXTURE))
        enriched["daily"]["apparent_temperature_max"] = [38.8, 33.0]
        enriched["daily"]["apparent_temperature_min"] = [28.0, 24.0]
        enriched["daily"]["uv_index_max"] = [9.3, 6.1]
        enriched["daily"]["windgusts_10m_max"] = [22.7, 15.0]
        enriched["daily"]["relative_humidity_2m_max"] = [99, 70]
        enriched["daily"]["sunrise"] = ["2026-08-01T00:53", "2026-08-02T00:53"]
        enriched["daily"]["sunset"] = ["2026-08-01T12:53", "2026-08-02T12:52"]
        respx.get(open_meteo._BASE_URL).mock(return_value=httpx.Response(200, json=enriched))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        rainy, _ = readings
        assert rainy.feels_like_max_c == pytest.approx(38.8)
        assert rainy.feels_like_min_c == pytest.approx(28.0)
        assert rainy.uv_index_max == pytest.approx(9.3)
        assert rainy.wind_gust_kph == pytest.approx(22.7)
        assert rainy.sunrise == "2026-08-01T00:53"
        assert rainy.sunset == "2026-08-01T12:53"
        assert rainy.humidity == pytest.approx(0.99)  # converted from 99% to a 0.0-1.0 fraction
        # precipitation_mm AND humidity both present now.
        assert rainy.completeness == pytest.approx(1.0)

    @respx.mock
    async def test_missing_new_fields_degrade_to_none_not_an_error(
        self, adapter: OpenMeteoAdapter
    ) -> None:
        """The original fixture has none of the new fields — every adapter
        response, old or new, must still parse cleanly."""
        respx.get(open_meteo._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        rainy, _ = readings
        assert rainy.feels_like_max_c is None
        assert rainy.uv_index_max is None
        assert rainy.wind_gust_kph is None
        assert rainy.sunrise is None
        assert rainy.sunset is None

    @respx.mock
    async def test_invalid_reading_is_dropped_not_fabricated(
        self, adapter: OpenMeteoAdapter
    ) -> None:
        bad_fixture = json.loads(json.dumps(_FIXTURE))
        # temp_max < temp_min on day 1 -> must be dropped, not coerced.
        bad_fixture["daily"]["temperature_2m_max"][0] = 10.0
        respx.get(open_meteo._BASE_URL).mock(return_value=httpx.Response(200, json=bad_fixture))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 1
        assert readings[0].date == date(2026, 8, 2)
