"""AttractionPort — abstract interface for attraction/activity recommendations.

Implementations can use LLM, static database, external APIs, or hybrid approaches.
"""

from typing import Protocol

from app.domain.entities.attractions import (
    AttractionRecommendation,
    AttractionType,
)
from app.domain.entities.trip import TripContext
from app.domain.entities.weather_intelligence import WeatherIntelligence


class AttractionPort(Protocol):
    """Port for fetching attraction recommendations for a trip."""

    async def get_recommendations(
        self,
        *,
        trip_context: TripContext,
        weather_intelligence: WeatherIntelligence,
        preferred_types: tuple[AttractionType, ...] = (),
    ) -> AttractionRecommendation:
        """Return weather-aware attraction recommendations for the trip.

        Args:
            trip_context: User's destination, dates, interests, travel style
            weather_intelligence: Deterministic weather analysis for the period
            preferred_types: Filter to specific attraction types (from interests)

        Returns:
            AttractionRecommendation with daily suggestions
        """
        ...


__all__ = ["AttractionPort"]