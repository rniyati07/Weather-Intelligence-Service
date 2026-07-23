"""Unit tests for shared normalization helpers and condition-mapping tables.

Offline, no network — pure-function tests for the conversion/validation
logic shared by every provider adapter.
"""

import pytest

from app.domain.entities.weather import WeatherCondition
from app.infrastructure.providers.condition_maps import (
    map_open_meteo_condition,
    map_openweather_condition,
    map_weatherapi_condition,
)
from app.infrastructure.providers.normalization import (
    compute_completeness,
    fahrenheit_to_celsius,
    is_valid_reading,
    kelvin_to_celsius,
    mph_to_kph,
    mps_to_kph,
    percent_to_fraction,
)


class TestUnitConversion:
    def test_kelvin_to_celsius(self) -> None:
        assert kelvin_to_celsius(273.15) == pytest.approx(0.0)
        assert kelvin_to_celsius(300.0) == pytest.approx(26.85)

    def test_fahrenheit_to_celsius(self) -> None:
        assert fahrenheit_to_celsius(32.0) == pytest.approx(0.0)
        assert fahrenheit_to_celsius(212.0) == pytest.approx(100.0)

    def test_mps_to_kph(self) -> None:
        assert mps_to_kph(1.0) == pytest.approx(3.6)

    def test_mph_to_kph(self) -> None:
        assert mph_to_kph(1.0) == pytest.approx(1.60934)

    def test_percent_to_fraction(self) -> None:
        assert percent_to_fraction(70.0) == pytest.approx(0.7)

    def test_percent_to_fraction_clamps_out_of_range(self) -> None:
        assert percent_to_fraction(150.0) == 1.0
        assert percent_to_fraction(-10.0) == 0.0


class TestCompleteness:
    def test_both_fields_present(self) -> None:
        assert compute_completeness(precipitation_mm=1.0, humidity=0.5) == 1.0

    def test_one_field_present(self) -> None:
        assert compute_completeness(precipitation_mm=1.0, humidity=None) == 0.5

    def test_no_fields_present(self) -> None:
        assert compute_completeness(precipitation_mm=None, humidity=None) == 0.0

    def test_zero_value_counts_as_present(self) -> None:
        assert compute_completeness(precipitation_mm=0.0, humidity=0.0) == 1.0


class TestValidation:
    def test_valid_reading_passes(self) -> None:
        assert is_valid_reading(
            temp_min_c=20.0, temp_max_c=30.0, precipitation_probability=0.5, wind_speed_kph=10.0
        )

    def test_temp_max_below_temp_min_is_invalid(self) -> None:
        assert not is_valid_reading(
            temp_min_c=30.0, temp_max_c=20.0, precipitation_probability=0.5, wind_speed_kph=10.0
        )

    def test_out_of_range_probability_is_invalid(self) -> None:
        assert not is_valid_reading(
            temp_min_c=20.0, temp_max_c=30.0, precipitation_probability=1.5, wind_speed_kph=10.0
        )

    def test_negative_wind_is_invalid(self) -> None:
        assert not is_valid_reading(
            temp_min_c=20.0, temp_max_c=30.0, precipitation_probability=0.5, wind_speed_kph=-1.0
        )


class TestConditionMaps:
    def test_open_meteo_known_code(self) -> None:
        assert map_open_meteo_condition(0) == WeatherCondition.CLEAR
        assert map_open_meteo_condition(95) == WeatherCondition.THUNDERSTORM

    def test_open_meteo_unmapped_code_falls_back(self) -> None:
        assert map_open_meteo_condition(999) == WeatherCondition.CLOUDY

    def test_openweather_known_code(self) -> None:
        assert map_openweather_condition(800) == WeatherCondition.CLEAR
        assert map_openweather_condition(200) == WeatherCondition.THUNDERSTORM

    def test_openweather_unmapped_code_falls_back(self) -> None:
        assert map_openweather_condition(999999) == WeatherCondition.CLOUDY

    def test_weatherapi_known_code(self) -> None:
        assert map_weatherapi_condition(1000) == WeatherCondition.CLEAR
        assert map_weatherapi_condition(1087) == WeatherCondition.THUNDERSTORM

    def test_weatherapi_unmapped_code_falls_back(self) -> None:
        assert map_weatherapi_condition(9999) == WeatherCondition.CLOUDY

    def test_every_weather_condition_is_reachable(self) -> None:
        # Provider-independence groundwork for Phase 6: every enum value must
        # be producible by at least one provider's mapping table.
        reachable: set[WeatherCondition] = set()
        for code in range(0, 100):
            reachable.add(map_open_meteo_condition(code))
        for code in range(200, 900):
            reachable.add(map_openweather_condition(code))
        for code in range(1000, 1300):
            reachable.add(map_weatherapi_condition(code))

        assert reachable == set(WeatherCondition)
