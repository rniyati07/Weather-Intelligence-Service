"""Chat intent — the dispatch signal deciding which expensive steps
(weather fetch, attraction fetch) a turn actually needs.

Gemini classifies intent contextually now, as part of the same structured
extraction call that reads destination/dates/interests (see
`ChatOrchestrator`/`EntityExtractor`) — "which day is best?" means something
different depending on the established trip and the turns before it, which
a keyword match cannot see. `classify_intent` below is no longer the primary
path; it is the deterministic fallback used when Gemini's own `intent` field
is missing, unrecognized, or the extraction call failed outright — the
"backend may still use deterministic guards for clearly invalid/unsafe
states" the architecture keeps room for.
"""

from enum import StrEnum

from app.domain.entities.trip import TripContext


class ChatIntent(StrEnum):
    """What kind of turn this is, once the entities in it are known."""

    TRIP_PLANNING = "trip_planning"
    ITINERARY_REQUEST = "itinerary_request"
    WEATHER_QUESTION = "weather_question"
    RECOMMENDATION_REQUEST = "recommendation_request"
    PACKING_REQUEST = "packing_request"
    GENERAL_CHAT = "general_chat"


#: First-match-wins, most-specific first: "itinerary" implies recommendations
#: are wanted too, so it must be checked before the recommendation keywords;
#: packing is checked before weather so "what should I pack if it's hot"
#: lands on packing, the more specific ask.
_ITINERARY_KEYWORDS = (
    "itinerary", "day plan", "day-by-day", "daily plan", "full plan", "schedule my",
)
_PACKING_KEYWORDS = ("pack", "packing", "bring", "wear", "luggage")
_RECOMMENDATION_KEYWORDS = (
    "recommend", "suggest", "suggestion", "places", "place near", "attraction",
    "things to do", "what to do", "what can i do", "where should", "activities",
    "active", "beach", "beaches", "museum", "nightlife", "restaurant", "hike", "hiking",
    "shopping", "nearby", "near ",
    # Stays and sports (Phase 1/2 categories) need their own coverage here too
    # — this list feeds intent classification, a separate concern from
    # `_interests_to_attraction_types`'s category mapping, which already had
    # these words for a *recognized* recommendation turn. Without them here,
    # a message like "what about sports to do" fell through every keyword
    # list straight to GENERAL_CHAT whenever this fallback ran (Gemini's own
    # classification unavailable), skipping the attraction fetch entirely.
    "hotel", "hotels", "stay", "guest house", "hostel", "accommodation", "lodging",
    "sport", "sports", "tennis", "golf", "football", "cricket",
)
_WEATHER_KEYWORDS = (
    "weather", "rain", "rainy", "sunny", "sunshine", "temperature", "hot", "cold",
    "forecast", "humid", "windy", "wind", "storm", "cloudy",
    # "Which day is best?" is this product's own canonical example question
    # (PRD, README, rebuild architecture doc all use it) — it was matching
    # none of these lists and falling through to GENERAL_CHAT. A best/worst
    # *day* judgment is exactly the deterministic engine's own output
    # (bestDays/worstDays), so it belongs here, not RECOMMENDATION_REQUEST.
    "which day", "best day", "worst day", "which is the best", "which is the worst",
)


def classify_intent(message: str, context: TripContext) -> ChatIntent:
    """Keyword fallback — used only when Gemini's own intent classification
    is unavailable (extraction failed) or came back as something this
    codebase doesn't recognize.

    An incomplete context is always `TRIP_PLANNING`: with no resolved
    destination and dates there is nothing to recommend or forecast, so no
    other label could be correct regardless of wording — asking "which day
    is best for beaches?" before a destination exists is still a planning
    turn, not a recommendation the assistant can act on yet. This guard
    applies before Gemini's classification is even consulted, not only here.
    """
    if not context.is_complete:
        return ChatIntent.TRIP_PLANNING

    lowered = message.lower()

    if any(keyword in lowered for keyword in _ITINERARY_KEYWORDS):
        return ChatIntent.ITINERARY_REQUEST
    if any(keyword in lowered for keyword in _PACKING_KEYWORDS):
        return ChatIntent.PACKING_REQUEST
    if any(keyword in lowered for keyword in _RECOMMENDATION_KEYWORDS):
        return ChatIntent.RECOMMENDATION_REQUEST
    if any(keyword in lowered for keyword in _WEATHER_KEYWORDS):
        return ChatIntent.WEATHER_QUESTION

    return ChatIntent.GENERAL_CHAT


__all__ = ["ChatIntent", "classify_intent"]
