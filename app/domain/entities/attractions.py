"""Attraction entities — weather-aware place/activity recommendations.

These are the structured recommendations the chat orchestrator uses to build
the LLM prompt. They are distinct from the deterministic weather intelligence
and can be provided by different backends (LLM, static DB, external API).
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal


class AttractionType(StrEnum):
    """Categories of attractions/activities."""

    BEACH = "beach"
    MUSEUM = "museum"
    LANDMARK = "landmark"
    VIEWPOINT = "viewpoint"
    RESTAURANT = "restaurant"
    CULTURAL_SITE = "cultural_site"
    OUTDOOR_ACTIVITY = "outdoor_activity"
    INDOOR_ACTIVITY = "indoor_activity"
    NATURE = "nature"
    SHOPPING = "shopping"
    NIGHTLIFE = "nightlife"
    WELLNESS = "wellness"
    WILDLIFE = "wildlife"
    ADVENTURE = "adventure"
    FAMILY = "family"
    PHOTOGRAPHY = "photography"
    FOOD = "food"
    HIKING = "hiking"
    WATER_SPORTS = "water_sports"
    HOTEL = "hotel"
    GUEST_HOUSE = "guest_house"
    SPORTS_FACILITY = "sports_facility"


class WeatherSuitability(StrEnum):
    """How weather affects this attraction."""

    IDEAL = "ideal"           # Weather makes this a great choice
    GOOD = "good"             # Weather is fine for this
    NEUTRAL = "neutral"       # Weather neither helps nor hurts
    POOR = "poor"             # Weather makes this less enjoyable
    UNSUITABLE = "unsuitable" # Weather makes this a bad choice


@dataclass(frozen=True, slots=True)
class Attraction:
    """A single recommended place or activity."""

    id: str
    name: str
    type: AttractionType
    description: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    # Weather influence on this attraction
    weather_suitability: WeatherSuitability = WeatherSuitability.NEUTRAL
    weather_notes: str | None = None
    # Best time of day (if weather-dependent)
    best_time: str | None = None
    # Estimated duration in hours
    duration_hours: float | None = None
    # Cost level
    cost_level: Literal["free", "low", "medium", "high"] | None = None
    # Tags for filtering
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DailyAttractions:
    """Attractions recommended for a specific day."""

    date: date
    location_id: str  # "lat,lon" key
    attractions: tuple[Attraction, ...]

    def by_type(self, attraction_type: AttractionType) -> tuple[Attraction, ...]:
        return tuple(a for a in self.attractions if a.type == attraction_type)

    def suitable_for_weather(
        self, min_suitability: WeatherSuitability = WeatherSuitability.GOOD
    ) -> tuple[Attraction, ...]:
        """Filter attractions suitable for current weather."""
        order = {
            WeatherSuitability.IDEAL: 5,
            WeatherSuitability.GOOD: 4,
            WeatherSuitability.NEUTRAL: 3,
            WeatherSuitability.POOR: 2,
            WeatherSuitability.UNSUITABLE: 1,
        }
        min_rank = order[min_suitability]
        return tuple(a for a in self.attractions if order[a.weather_suitability] >= min_rank)


@dataclass(frozen=True, slots=True)
class AttractionRecommendation:
    """Complete attraction recommendations for a trip period."""

    location_id: str
    period_start: date
    period_end: date
    daily: tuple[DailyAttractions, ...]

    def for_date(self, date: date) -> DailyAttractions | None:
        for day in self.daily:
            if day.date == date:
                return day
        return None


__all__ = [
    "Attraction",
    "AttractionType",
    "WeatherSuitability",
    "DailyAttractions",
    "AttractionRecommendation",
]