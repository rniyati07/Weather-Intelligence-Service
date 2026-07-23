"""Meteostat adapter: historical fixture -> expected `NormalizedReading`.

Meteostat has no native condition code, so condition is derived from
precipitation/snow/temperature (a documented approximation — see the
adapter's module docstring), and `precipitation_probability` is 1.0/0.0
(observed fact, not a forecast).
"""

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app.domain.entities.weather import WeatherCondition
from app.domain.ports.weather_provider import DataClass
from app.infrastructure.providers import meteostat
from app.infrastructure.providers.meteostat import MeteostatAdapter

_FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "providers" / "meteostat_daily.json").read_text()
)


@pytest.fixture
def adapter() -> MeteostatAdapter:
    return MeteostatAdapter(
        httpx.AsyncClient(), api_key="test-key", retry_attempts=2, retry_backoff_seconds=0.01
    )


class TestIsConfigured:
    def test_configured_when_key_present(self, adapter: MeteostatAdapter) -> None:
        assert adapter.is_configured() is True

    def test_not_configured_when_key_absent(self) -> None:
        adapter = MeteostatAdapter(
            httpx.AsyncClient(), api_key="", retry_attempts=2, retry_backoff_seconds=0.01
        )
        assert adapter.is_configured() is False


def test_is_historical() -> None:
    assert MeteostatAdapter.data_class == DataClass.HISTORICAL


class TestFetch:
    @respx.mock
    async def test_fixture_maps_to_expected_readings(self, adapter: MeteostatAdapter) -> None:
        respx.get(meteostat._BASE_URL).mock(return_value=httpx.Response(200, json=_FIXTURE))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 2
        rainy, clear = readings

        assert rainy.date == date(2026, 8, 1)
        assert rainy.temp_max_c == 31.0
        assert rainy.temp_min_c == 24.0
        assert rainy.wind_speed_kph == 18.3  # already km/h, no conversion
        assert rainy.precipitation_mm == pytest.approx(12.4)
        assert rainy.precipitation_probability == 1.0  # observed: it rained
        assert rainy.condition == WeatherCondition.RAIN
        assert rainy.source_class == "historical"
        assert rainy.humidity is None
        assert rainy.completeness == pytest.approx(0.5)  # precip present, humidity never available

        assert clear.date == date(2026, 8, 2)
        assert clear.precipitation_mm == pytest.approx(0.0)
        assert clear.precipitation_probability == 0.0  # observed: it didn't rain
        assert clear.condition == WeatherCondition.CLEAR

    @respx.mock
    async def test_snow_field_derives_snow_condition(self, adapter: MeteostatAdapter) -> None:
        snowy_fixture = json.loads(json.dumps(_FIXTURE))
        snowy_fixture["data"][0]["snow"] = 5.0
        snowy_fixture["data"][0]["tmax"] = -2.0
        snowy_fixture["data"][0]["tmin"] = -8.0
        respx.get(meteostat._BASE_URL).mock(return_value=httpx.Response(200, json=snowy_fixture))

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert readings[0].condition == WeatherCondition.SNOW

    @respx.mock
    async def test_day_missing_temperature_is_dropped(self, adapter: MeteostatAdapter) -> None:
        incomplete_fixture = json.loads(json.dumps(_FIXTURE))
        incomplete_fixture["data"][0]["tmax"] = None
        respx.get(meteostat._BASE_URL).mock(
            return_value=httpx.Response(200, json=incomplete_fixture)
        )

        readings = await adapter.fetch(15.25, 74.125, date(2026, 8, 1), date(2026, 8, 2))

        assert len(readings) == 1
        assert readings[0].date == date(2026, 8, 2)
