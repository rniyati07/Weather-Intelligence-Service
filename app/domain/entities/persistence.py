"""Plain, framework-free records that cross the `WeatherRepository` port.

These mirror the persisted schema (TRD §7.1) but are not ORM models — the
domain layer never imports SQLAlchemy. Infrastructure repositories translate
to and from these types; no ORM instance is ever returned across the port
boundary.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

RiskLevel = Literal["low", "moderate", "high"]
TravelAdvisory = Literal["proceed", "caution", "avoid"]


@dataclass(frozen=True, slots=True)
class Location:
    """A canonical place, keyed by a stable, normalized coordinate string."""

    name: str
    latitude: float
    longitude: float
    normalized_key: str
    id: int | None = None


@dataclass(frozen=True, slots=True)
class RawWeatherReading:
    """One provider's raw + normalized payload for a location on a given date."""

    location_id: int
    provider: str
    fetched_at: datetime
    valid_date: date
    raw_payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    id: int | None = None


@dataclass(frozen=True, slots=True)
class DailyIntelligenceRecord:
    """Computed per-day intelligence, stamped with the rule config version behind it."""

    location_id: int
    date: date
    risk_level: RiskLevel
    risk_factors: list[dict[str, Any]]
    activity_scores: dict[str, Any]
    packing: list[str]
    travel_advisory: TravelAdvisory
    rule_config_version: str
    generated_at: datetime
    id: int | None = None
