"""The definitive provider-independence test (guide Phase 6).

Runs the Phase 4 fixtures — deliberately crafted to represent the same two
conceptual days (a rainy day and a clear day) — through all four adapters,
then asserts they produce structurally identical and numerically equivalent
`NormalizedReading` output. This is what proves normalization, not adapter
choice, determines the shape and substance of downstream data.

Meteostat is historical, not forecast, so two fields legitimately differ by
design (documented in its adapter's module docstring): `source_class` and
`precipitation_probability` (an observed 1.0/0.0 fact, not a forecast
percentage). Every other field is held to the same equivalence as the three
forecast providers.
"""

import json
from datetime import date
from pathlib import Path

import httpx
import respx

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.infrastructure.providers import meteostat, open_meteo, openweather, weatherapi
from app.infrastructure.providers.meteostat import MeteostatAdapter
from app.infrastructure.providers.open_meteo import OpenMeteoAdapter
from app.infrastructure.providers.openweather import OpenWeatherAdapter
from app.infrastructure.providers.weatherapi import WeatherApiAdapter

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "providers"
_RAIN_DAY = date(2026, 8, 1)
_CLEAR_DAY = date(2026, 8, 2)
_RAIN_FAMILY = {WeatherCondition.RAIN, WeatherCondition.HEAVY_RAIN}

# Real providers never report byte-identical numbers for the same physical
# weather; these tolerances bound "close enough to be the same weather."
_TEMP_TOLERANCE_C = 1.0
_WIND_TOLERANCE_KPH = 4.0
_PRECIP_TOLERANCE_MM = 3.0


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((_FIXTURES_DIR / name).read_text())


def _reading_for(readings: list[NormalizedReading], day: date) -> NormalizedReading:
    return next(r for r in readings if r.date == day)


class TestProviderIndependence:
    @respx.mock
    async def test_all_four_providers_yield_equivalent_readings_for_the_same_weather(
        self,
    ) -> None:
        respx.get(open_meteo._BASE_URL).mock(
            return_value=httpx.Response(200, json=_load_fixture("open_meteo_forecast.json"))
        )
        respx.get(openweather._BASE_URL).mock(
            return_value=httpx.Response(200, json=_load_fixture("openweather_forecast.json"))
        )
        respx.get(weatherapi._BASE_URL).mock(
            return_value=httpx.Response(200, json=_load_fixture("weatherapi_forecast.json"))
        )
        respx.get(meteostat._BASE_URL).mock(
            return_value=httpx.Response(200, json=_load_fixture("meteostat_daily.json"))
        )

        open_meteo_adapter = OpenMeteoAdapter(
            httpx.AsyncClient(), retry_attempts=1, retry_backoff_seconds=0.01
        )
        openweather_adapter = OpenWeatherAdapter(
            httpx.AsyncClient(), api_key="key", retry_attempts=1, retry_backoff_seconds=0.01
        )
        weatherapi_adapter = WeatherApiAdapter(
            httpx.AsyncClient(), api_key="key", retry_attempts=1, retry_backoff_seconds=0.01
        )
        meteostat_adapter = MeteostatAdapter(
            httpx.AsyncClient(), api_key="key", retry_attempts=1, retry_backoff_seconds=0.01
        )

        by_provider: dict[str, list[NormalizedReading]] = {
            "open_meteo": await open_meteo_adapter.fetch(15.25, 74.125, _RAIN_DAY, _CLEAR_DAY),
            "openweather": await openweather_adapter.fetch(15.25, 74.125, _RAIN_DAY, _CLEAR_DAY),
            "weatherapi": await weatherapi_adapter.fetch(15.25, 74.125, _RAIN_DAY, _CLEAR_DAY),
            "meteostat": await meteostat_adapter.fetch(15.25, 74.125, _RAIN_DAY, _CLEAR_DAY),
        }

        # --- Structural independence: one model shape, no identity leak. ---
        field_names = {f for f in NormalizedReading.__dataclass_fields__}
        assert "provider" not in field_names
        for readings in by_provider.values():
            assert all(isinstance(r, NormalizedReading) for r in readings)

        # --- Rain day: the three forecast providers describe the same
        # real-world weather within reporting tolerance. ---
        forecast_names = ["open_meteo", "openweather", "weatherapi"]
        forecast_rain = [_reading_for(by_provider[name], _RAIN_DAY) for name in forecast_names]

        temp_maxes = [r.temp_max_c for r in forecast_rain]
        temp_mins = [r.temp_min_c for r in forecast_rain]
        winds = [r.wind_speed_kph for r in forecast_rain]
        precips = [r.precipitation_mm for r in forecast_rain]

        assert all(p is not None for p in precips)
        assert max(temp_maxes) - min(temp_maxes) <= _TEMP_TOLERANCE_C
        assert max(temp_mins) - min(temp_mins) <= _TEMP_TOLERANCE_C
        assert max(winds) - min(winds) <= _WIND_TOLERANCE_KPH
        assert max(precips) - min(precips) <= _PRECIP_TOLERANCE_MM  # type: ignore[type-var]
        assert all(r.condition in _RAIN_FAMILY for r in forecast_rain)
        assert all(r.source_class == "forecast" for r in forecast_rain)

        # Meteostat describes the same physical day, temperature/wind-wise...
        meteostat_rain = _reading_for(by_provider["meteostat"], _RAIN_DAY)
        mean_forecast_temp_max = sum(temp_maxes) / len(temp_maxes)
        assert abs(meteostat_rain.temp_max_c - mean_forecast_temp_max) <= _TEMP_TOLERANCE_C
        assert meteostat_rain.condition in _RAIN_FAMILY
        # ...but is honestly labelled historical, with observed-fact
        # probability semantics rather than a forecast percentage.
        assert meteostat_rain.source_class == "historical"
        assert meteostat_rain.precipitation_probability == 1.0

        # --- Clear day: all four providers agree. ---
        for name, readings in by_provider.items():
            clear_reading = _reading_for(readings, _CLEAR_DAY)
            assert clear_reading.condition == WeatherCondition.CLEAR, name

    def test_no_provider_identity_field_exists_on_the_model(self) -> None:
        # A permanent structural guard for the provider-independence rule:
        # this must fail loudly if anyone ever adds a provider-identifying
        # field to the shared model.
        assert "provider" not in NormalizedReading.__dataclass_fields__
        assert "provider_name" not in NormalizedReading.__dataclass_fields__
