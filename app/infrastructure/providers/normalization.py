"""Shared normalization helpers: unit conversion, completeness, and validation.

Every adapter converts units exactly once, at this boundary, before
constructing a `NormalizedReading` — nothing downstream ever sees a raw
provider unit. `_OPTIONAL_FIELDS` fixes what "completeness" means so every
adapter computes it identically.
"""

import logging

logger = logging.getLogger(__name__)

_OPTIONAL_FIELD_COUNT = 2  # precipitation_mm, humidity — API Spec §9.9


def kelvin_to_celsius(kelvin: float) -> float:
    return kelvin - 273.15


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - 32.0) * 5.0 / 9.0


def mps_to_kph(meters_per_second: float) -> float:
    return meters_per_second * 3.6


def mph_to_kph(miles_per_hour: float) -> float:
    return miles_per_hour * 1.60934


def percent_to_fraction(percent: float) -> float:
    """Clamp to `0.0-1.0` — some providers occasionally report slightly out-of-range values."""
    return max(0.0, min(1.0, percent / 100.0))


def compute_completeness(
    *, precipitation_mm: float | None, humidity: float | None
) -> float:
    """Fraction of the expected optional fields present (feeds `travelConfidence`)."""
    present = sum(1 for value in (precipitation_mm, humidity) if value is not None)
    return present / _OPTIONAL_FIELD_COUNT


def is_valid_reading(
    *, temp_min_c: float, temp_max_c: float, precipitation_probability: float, wind_speed_kph: float
) -> bool:
    """Range-check a reading. Invalid readings are dropped, never fabricated or coerced."""
    if temp_max_c < temp_min_c:
        return False
    if not (0.0 <= precipitation_probability <= 1.0):
        return False
    return wind_speed_kph >= 0.0
