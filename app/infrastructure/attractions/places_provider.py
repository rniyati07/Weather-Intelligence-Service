"""`AttractionPort` backed by a real `PlacesPort` — the fix for issue 4.

Replaces the previous `LlmAttractionProvider`, which asked an LLM to invent
attraction names, coordinates, and addresses directly. That implementation is
removed rather than kept as a fallback: a "fallback" that hallucinates places
is not a degraded version of this feature, it is the exact defect this class
exists to eliminate, and an unlabelled toggle between them would be a latent
way to reintroduce it. See the stabilization report for the full decision.

Ranking and description text are entirely deterministic
(`attraction_matching.py`) — no LLM call happens in this class at all. The
chat orchestrator's own LLM call, made afterwards over the resulting
structured data, is where any natural-language treatment of these places
happens; by then every name in its prompt already came from a real place.
"""

import logging

from app.domain.engines.recommendation.attraction_matching import build_attraction_recommendation
from app.domain.entities.attractions import AttractionRecommendation, AttractionType
from app.domain.entities.trip import TripContext
from app.domain.entities.weather_intelligence import WeatherIntelligence
from app.domain.ports.attractions import AttractionPort
from app.domain.ports.places import PlacesPort, PlacesUnavailableError

logger = logging.getLogger(__name__)

#: Used when the conversation hasn't established any interests yet — broad
#: enough to give a first-time "what should I do" question a real answer.
_DEFAULT_CATEGORIES: tuple[AttractionType, ...] = (
    AttractionType.LANDMARK,
    AttractionType.BEACH,
    AttractionType.MUSEUM,
    AttractionType.RESTAURANT,
)


class PlacesBackedAttractionProvider(AttractionPort):
    """Fetches real places via `PlacesPort`, ranks them deterministically."""

    def __init__(self, places: PlacesPort) -> None:
        self._places = places

    async def get_recommendations(
        self,
        *,
        trip_context: TripContext,
        weather_intelligence: WeatherIntelligence,
        preferred_types: tuple[AttractionType, ...] = (),
    ) -> AttractionRecommendation:
        assert trip_context.destination is not None
        categories = preferred_types or _DEFAULT_CATEGORIES

        try:
            places = await self._places.search(
                latitude=trip_context.destination.latitude,
                longitude=trip_context.destination.longitude,
                categories=categories,
            )
        except PlacesUnavailableError as exc:
            # Degrade, don't fail the whole chat turn: weather intelligence
            # is still useful on its own. Every day gets an empty attraction
            # list — never a fabricated one — and the chat prompt says so
            # explicitly, so the LLM explains the limitation instead of
            # inventing around it.
            logger.warning("places_unavailable: %s", exc)
            places = []

        return build_attraction_recommendation(
            trip_context=trip_context,
            weather_intelligence=weather_intelligence,
            places=places,
        )


__all__ = ["PlacesBackedAttractionProvider"]
