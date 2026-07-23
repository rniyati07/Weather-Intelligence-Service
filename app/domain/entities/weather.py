"""`NormalizedReading`: the one internal weather model every provider adapter produces.

Mirrors API & Data Contract Specification §9.9 field-for-field. After this
boundary, nothing downstream can tell which provider supplied the data —
provider independence is a hard rule (guide §5.3): provider identity never
travels inside this object, only in logs and `GET /providers/health`.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

# Mirrors `domain.ports.weather_provider.DataClass` by value, not by import:
# that port returns `NormalizedReading`, so importing `DataClass` from it here
# would create a circular import between the two domain modules.
SourceClass = Literal["forecast", "historical"]


class WeatherCondition(StrEnum):
    """Normalized internal condition vocabulary (API Spec §10)."""

    CLEAR = "clear"
    PARTLY_CLOUDY = "partly_cloudy"
    CLOUDY = "cloudy"
    RAIN = "rain"
    HEAVY_RAIN = "heavy_rain"
    THUNDERSTORM = "thunderstorm"
    SNOW = "snow"
    FOG = "fog"


@dataclass(frozen=True, slots=True)
class NormalizedReading:
    """One day's provider-agnostic weather reading.

    `completeness` is the fraction of expected optional fields
    (`precipitation_mm`, `humidity`) present on this reading — it feeds
    `travelConfidence` in Phase 7. `source_class` records whether this came
    from a forecast or historical provider.
    """

    date: date
    temp_min_c: float
    temp_max_c: float
    precipitation_probability: float
    wind_speed_kph: float
    condition: WeatherCondition
    completeness: float
    source_class: SourceClass
    precipitation_mm: float | None = None
    humidity: float | None = None
