"""ChatOrchestrator — the conversational travel assistant use case.

Orchestrates the full chat flow:
1. Load/create conversation
2. Gemini reads conversation history + TripContext + the new message and
   extracts a structured request in one call (destination, dates, duration,
   interests, travel style, pace, search area, intent) — a deterministic
   regex heuristic runs only if that call itself fails (see `EntityExtractor`)
3. Backend validates/normalizes the extraction (date parsing, the existing
   date-range rules, geocoding, destination-ambiguity detection) and updates
   TripContext
4. If incomplete: generate clarifying question
5. If complete: resolve intent (Gemini's classification, with a keyword
   fallback), fetch only the backend capabilities that intent needs
6. Generate conversational response via Gemini, grounded in only that data
   (structured fallback on failure)
7. Save conversation state

This keeps one orchestrator and two Gemini calls per turn — understanding,
then response generation — never an agent loop or tool-calling framework
(Bible ADR-006/011). Gemini never touches a coordinate, a weather number, a
score, or a place name directly: it reads raw text out of a message and
writes raw text back in the response; every fact in between is fetched or
computed by the backend and merely restated.
"""

import contextlib
import json
import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.application.use_cases.cached_intelligence import IntelligenceUseCase
from app.domain.entities.attractions import (
    Attraction,
    AttractionRecommendation,
    AttractionType,
)
from app.domain.entities.conversation import Conversation, Message
from app.domain.entities.trip import (
    MISSING_DESTINATION,
    MISSING_END_DATE,
    MISSING_START_DATE,
    GeocodedPlace,
    TripContext,
    parse_iso_date,
)
from app.domain.entities.weather_intelligence import WeatherIntelligence
from app.domain.ports.attractions import AttractionPort
from app.domain.ports.conversation import ConversationRepository
from app.domain.ports.geocoding import GeocodingPort
from app.domain.rules.date_range import InvalidDateRangeError
from app.domain.rules.date_range import validate_date_range as validate_trip_date_range
from app.domain.rules.intent import ChatIntent, classify_intent
from app.infrastructure.ai.llm_client import LlmClient, LlmClientError, LlmTimeoutError

logger = logging.getLogger(__name__)


class _MalformedExtractionError(Exception):
    """Gemini's extraction call returned syntactically valid JSON that
    wasn't a JSON object — treated the same as a call failure, never as
    "nothing extracted"."""


def _format_history(messages: Sequence[Message]) -> str:
    """Render a bounded window of turns as `Role: text` lines.

    Shared by the extraction prompt and the response-generation prompt so
    the two Gemini calls see conversation history in exactly the same
    shape — the "context understanding" the extraction call does and the
    "final response" the second call writes are reading the same story.
    """
    lines = [f"{'User' if msg.role == 'user' else 'Assistant'}: {msg.content}" for msg in messages]
    return "\n".join(lines) if lines else "(start of conversation)"


def _uv_category(uv_index: float) -> str:
    """WHO UV Index categories — a public, standard scale, not invented."""
    if uv_index >= 11:
        return "extreme"
    if uv_index >= 8:
        return "very high"
    if uv_index >= 6:
        return "high"
    if uv_index >= 3:
        return "moderate"
    return "low"


def _local_clock_time(iso_utc: str | None, timezone_name: str | None) -> str | None:
    """A UTC ISO datetime (Open-Meteo's `sunrise`/`sunset` shape) rendered in
    the destination's own local time — a bare UTC timestamp would mislead
    rather than help ("sunset at 12:53" means nothing to a traveler unless
    it's already in their destination's clock). Falls back to UTC if the
    destination's timezone wasn't resolved, rather than guessing one."""
    if not iso_utc:
        return None
    try:
        moment = datetime.fromisoformat(iso_utc)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    if timezone_name:
        with contextlib.suppress(KeyError, ValueError):
            moment = moment.astimezone(ZoneInfo(timezone_name))
    return moment.strftime("%I:%M %p").lstrip("0")


#: Turns kept in the prompt's conversation-history section. Bounded so a long
#: conversation doesn't grow the prompt (and therefore cost/latency)
#: unboundedly — recent context matters far more than early context once a
#: trip's essentials are already captured in `TripContext`.
_HISTORY_TURNS_IN_PROMPT = 6

#: Structured extraction is a read-and-report task, not a creative one — a
#: low temperature makes it far less likely to drop an explicitly-stated
#: destination or date on an unlucky sampling draw. Narrative generation
#: keeps the provider's own default (unset), since that response wants
#: natural variation; this constant is for the extraction call only.
_EXTRACTION_TEMPERATURE = 0.1

#: Places referenced per day when building the LLM prompt AND when
#: populating the structured `places` field on the response — one shared
#: cap so the two can never drift apart: the reply can't mention a place
#: absent from the structured list, and vice versa.
_PLACES_PER_DAY_IN_RESPONSE = 3

#: Same shared cap, raised for a turn that explicitly asked for detail —
#: matches `attraction_matching._MAX_PLACES_PER_DAY`, the most the engine
#: ever ranks for one day, so "raised" still means "every real place we
#: actually have", never an invented one.
_MAX_PLACES_PER_DAY_IN_RESPONSE = 6

#: A user who explicitly asks for a checklist, a full itinerary, or "every
#: day" wants a complete structured answer, not the terse 2-3 sentences
#: every other question gets. Live testing found the fixed terse/no-list
#: prompt rules actively fighting these requests: a packing "checklist" ask
#: got an outright refusal (the model had real data but no way to present
#: it within "no bullet lists, 3 sentences"), and "3 restaurants each day"
#: still got one restaurant per day because "name at most two or three
#: places" is a *whole-response* cap, not per-day.
_DETAIL_REQUEST_KEYWORDS = (
    "checklist", "itinerary", "detailed", "in detail", "guidelines",
    "each day", "every day", "day by day", "day-by-day", "full plan",
    "breakdown", "all the", "everything",
)


def _wants_detailed_response(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in _DETAIL_REQUEST_KEYWORDS)


#: Live-observed regression: once any specific interest (e.g. "food") gets
#: recorded on the trip, it never narrows back — `TripContext.interests`
#: only ever accumulates — so a later, broader ask ("proper itinerary with
#: viewpoints, cafes, beaches, monuments, things to do") stayed scoped to
#: just that one earlier category forever, and every place search kept
#: returning restaurants only. A message that explicitly asks "what's here"
#: in general must widen the search back out, not stay crowded out by
#: whatever narrow thing was mentioned first.
#: "itinerary" itself belongs here too, not just its synonyms — live-observed:
#: the turn that *establishes* a trip is always forced to `TRIP_PLANNING`
#: intent regardless of wording (so the trip-establishing turn always gets
#: full treatment; see `process_message`'s `was_complete_before_this_turn`
#: branch), which means "plan a trip to X, love food, give me a detailed
#: itinerary" never reaches the `ITINERARY_REQUEST` intent check below on
#: that first turn — only the phrase match here does.
_BROAD_ITINERARY_PHRASES = (
    "things to do", "places to visit", "places to see", "what to see",
    "what to do", "sightseeing", "what all is there", "itinerary",
    "day by day", "day-by-day", "full plan",
)
_BROAD_ITINERARY_SPREAD = (
    AttractionType.LANDMARK,
    AttractionType.VIEWPOINT,
    AttractionType.BEACH,
    AttractionType.MUSEUM,
    AttractionType.CULTURAL_SITE,
    AttractionType.RESTAURANT,
    AttractionType.SPORTS_FACILITY,
)


def _wants_broad_itinerary(message: str) -> bool:
    lowered = message.lower()
    return any(phrase in lowered for phrase in _BROAD_ITINERARY_PHRASES)


#: How many of the most recent user turns `_recent_user_text` joins.
_RECENT_USER_TURNS_FOR_BREADTH_CHECK = 3


def _recent_user_text(conversation: Conversation) -> str:
    """The last few user turns, joined — live-observed: a from-scratch
    itinerary ask that also names an ambiguous destination ("Udaipur,
    Rajasthan, give me a detailed itinerary") gets its category breadth
    computed on the *next* turn, once the destination is actually resolved —
    but that turn's own text is just the disambiguation reply ("1"), which
    carries none of the original wording. Checking `_wants_broad_itinerary`
    against the last few turns rather than only the current one means the
    itinerary ask one turn back still counts."""
    user_messages = [m.content for m in conversation.messages if m.role == "user"]
    return " ".join(user_messages[-_RECENT_USER_TURNS_FOR_BREADTH_CHECK:])

#: How many geocoding candidates a destination-clarification turn offers.
#: Mirrors `GeocodingPort.DEFAULT_SEARCH_LIMIT` — enough to disambiguate
#: without turning the question into a wall of options.
_MAX_CLARIFICATION_CANDIDATES = 5

#: Words a clarification reply might use instead of a bare digit ("the
#: first one"). Small and closed on purpose — anything not recognized here
#: falls through to re-asking rather than guessing which one was meant.
_ORDINAL_WORDS: dict[str, int] = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
}


def _is_ambiguous_candidates(candidates: list[GeocodedPlace], query: str) -> bool:
    """True when the top geocoding candidates plausibly name different places
    the user could actually mean.

    Country-diversity alone isn't enough: a fuzzy, population-ranked
    geocoder returns loosely similar-*sounding* places from anywhere in the
    world alongside a genuine match — live-observed: "varkala kerala"
    returning both "Varkala, India" (the obvious match) and
    "Varkalabiškės, Lithuania" (an unrelated village that happens to fold
    close enough to rank). Asking the user to disambiguate against a place
    they were never talking about is not the same failure mode as the
    intended case: a bare "Paris" resolving to Paris, France vs. Paris,
    Texas, where BOTH candidates are literally named "Paris". Restricting
    the country-diversity check to candidates whose name actually appears in
    what the user typed keeps the Paris case working while dropping the
    Varkala one.

    Country alone under-triggers: live-observed, "Manali" returns a 35k-
    population Chennai suburb (Tamil Nadu) ranked above the 8k-population
    Himalayan hill station (Himachal Pradesh) tourists actually mean —
    Open-Meteo's population ranking has no notion of tourism relevance, and
    both candidates share a country, so a country-only check silently
    accepts the wrong one. Comparing (country, region) instead catches any
    same-country candidates that are genuinely different places, while two
    rows for the same real place (identical country and region) still
    collapse to one identity and stay non-ambiguous.
    """
    if len(candidates) < 2:
        return False
    folded_query = query.strip().casefold()
    contenders = [c for c in candidates if c.name.strip().casefold() in folded_query]
    if len(contenders) < 2:
        return False
    identities = {(c.country_code or c.country, c.admin1) for c in contenders}
    return len(identities) > 1


#: A `searchArea` this far or further from the established trip destination
#: is treated as a bad extraction, not a genuine "near X" recentering — see
#: `ChatOrchestrator._resolve_search_area`. Generous enough to cover a whole
#: metro area or a nearby town (a state-sized radius), tight enough to catch
#: a fuzzy geocoder match landing in the wrong country.
_MAX_SEARCH_AREA_DISTANCE_KM = 150.0
_EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _clarification_label(candidate: GeocodedPlace) -> str:
    """A disambiguation-list line for one candidate — unlike
    `GeocodedPlace.display_name` (name + country only, fine for the normal
    single-result case), this always includes the region too. Live-observed:
    same-country candidates (the "Manali" case `_is_ambiguous_candidates`
    above now also catches) rendered as identical lines ("1. Manali, India"
    through "5. Manali, India") with `display_name` alone — nothing let the
    user actually tell them apart.
    """
    parts = [candidate.name, candidate.admin1, candidate.country]
    return ", ".join(part for part in parts if part)


def _geocoded_place_to_dict(place: GeocodedPlace) -> dict[str, object]:
    """JSON-safe form of a candidate, for `Message.metadata` round-tripping.

    Mirrors the shape `persistence/repositories.py` already uses to store
    `TripContext.destination` — same fields, same names, so a future reader
    isn't left guessing why two near-identical serializations exist.
    """
    return {
        "name": place.name,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "country": place.country,
        "country_code": place.country_code,
        "admin1": place.admin1,
        "timezone": place.timezone,
    }


#: What a good answer looks like, per intent.
#:
#: The same "2-5 paragraphs" instruction for every question is what produced
#: walls of prose that repeated the trip summary the interface already shows.
#: Each shape below says what to lead with and what to leave to the UI, so a
#: packing question gets a list and a day question gets a day — not the same
#: essay with different emphasis.
_INTENT_RESPONSE_SHAPES: dict[ChatIntent, str] = {
    ChatIntent.TRIP_PLANNING: (
        "give the headline verdict on the trip and what's driving it, like you're texting a "
        "friend the gist — the outlook, days and packing are already on screen, so add color "
        "rather than repeating the numbers"
    ),
    ChatIntent.ITINERARY_REQUEST: (
        "walk through the days like you're actually planning it with them — for each day, "
        "name the real spots and give each a little flavor: what it's known for, what's "
        "nearby, why it fits that day's weather. Easy to skim, not a dry list of names"
    ),
    ChatIntent.WEATHER_QUESTION: (
        "tell them what the day looks like and what that means for their plans, naturally"
    ),
    ChatIntent.RECOMMENDATION_REQUEST: (
        "recommend the real places above like you're tipping off a friend — what each is "
        "known for, why it's worth going, what's nearby. If none were provided, say so "
        "warmly and suggest what the weather makes sensible instead — never a bare 'None'"
    ),
    ChatIntent.PACKING_REQUEST: (
        "walk through what to pack and why, conversationally — a natural list is great here"
    ),
    ChatIntent.GENERAL_CHAT: "keep it short and friendly, like a quick reply",
}


def _attraction_to_dict(attraction: Attraction) -> dict[str, object]:
    """JSON-safe form of a place, for `Message.metadata` round-tripping.

    Field names match `PlaceSchema`'s wire shape rather than `Attraction`'s
    internals, so the metadata a restored conversation yields is the same
    shape the live `ChatResponse` carries and the frontend needs no second
    parser for it.

    Persisted because places are otherwise per-turn only: they are computed
    inside a chat turn and discarded, so reopening a conversation left the
    trip's places permanently empty even though the backend had found real
    ones. The trip workspace is trip-level state, not a property of whichever
    message happened to fetch it.
    """
    return {
        "name": attraction.name,
        "type": attraction.type.value,
        "latitude": attraction.latitude,
        "longitude": attraction.longitude,
        "address": attraction.address,
        "weatherSuitability": attraction.weather_suitability.value,
        "reason": attraction.weather_notes or "",
    }


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Result of processing a chat message."""

    conversation: Conversation
    response: str
    context_complete: bool
    missing_essentials: tuple[str, ...]
    intent: ChatIntent
    llm_generated: bool
    #: Real places the reply is grounded in — always a subset of what a
    #: `PlacesPort` call actually returned, never LLM-invented. Empty when
    #: this turn fetched no attractions (clarification turns, general chat).
    places: tuple[Attraction, ...] = ()
    #: Set only when this turn's response is a destination disambiguation
    #: question — the structured form of the candidates listed in `response`.
    destination_candidates: tuple[GeocodedPlace, ...] = ()


#: What `EntityExtractor._llm_extract`'s JSON keys (camelCase, matching the
#: structured-request field names) map onto internally — the rest of this
#: module works in snake_case throughout, so this is the one place the
#: convention boundary is crossed, and the one place an unrecognized or
#: `null` key is dropped rather than propagated.
_EXTRACTION_KEY_MAP: dict[str, str] = {
    "destination": "destination",
    "searchArea": "search_area",
    "startDate": "start_date",
    "endDate": "end_date",
    "duration": "duration",
    "interests": "interests",
    "travelStyle": "travel_style",
    "pace": "pace",
    "intent": "intent",
}


class EntityExtractor:
    """Turns one user message, read in context, into a structured request.

    Gemini is the primary path: one JSON-mode call sees the recent
    conversation, the `TripContext` already established, and the latest
    message, and returns destination/dates/duration/interests/travel style/
    pace/search area/intent as JSON — genuine natural-language
    understanding, not a regex over capitalized words. A small keyword/regex
    heuristic exists only as the fallback used when that call itself fails
    (network, timeout, or an unparseable response) — never blended with a
    successful Gemini result, and never run first. Dates returned by either
    path are strings — the orchestrator runs them through `parse_iso_date`
    before they ever reach `TripContext.merge`, which is typed `date | None`
    and does not coerce.
    """

    #: Sentence position alone is not a signal a word is a proper noun —
    #: "We are visiting Bali" capitalizes "We" for grammar, not because it
    #: names a place. Filtering by word alone (not position) is deliberate:
    #: "Goa, August 20 to 23" opens *with* the real destination, so dropping
    #: whatever comes first would break the more common case to fix the
    #: rarer one. Month names are included because a date phrase sitting
    #: next to the destination is exactly what triggers this path.
    #: Used only by the fallback heuristic below — Gemini needs no stopword
    #: list, it reads the sentence.
    _NON_DESTINATION_WORDS = frozenset(
        {
            "i", "am", "im", "going", "to", "visit", "visiting", "travel", "travelling",
            "traveling", "trip", "planning", "plan", "want", "like", "love", "for",
            "days", "day", "week", "weekend", "month", "we", "are", "my", "our", "us",
            "they", "their", "he", "she", "it", "this", "that", "next", "family",
            "friends", "parents", "of", "a", "an", "the", "and", "with",
            "january", "february", "march", "april", "may", "june", "july",
            "august", "september", "october", "november", "december",
            # Question words and common request phrasing — without these, a
            # follow-up question ("Which day is best?", "Can you find me a
            # hotel?") had its leading capitalized word misread as a
            # destination by this heuristic. Only reachable when the LLM call
            # itself fails (this heuristic is the fallback path), but a
            # question is exactly the shape of message that path must not
            # get wrong, since a mid-conversation follow-up is exactly when
            # a destination should almost never be re-extracted.
            "which", "what", "who", "where", "when", "how", "why", "can", "could",
            "would", "should", "do", "does", "did", "is", "was", "were",
            "you", "your", "me", "find", "any", "some", "good", "nice", "best",
            "places", "place",
        }
    )

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def extract(
        self,
        message: str,
        current_context: TripContext,
        history: Sequence[Message],
    ) -> dict[str, Any]:
        """Extract a structured request from `message`, in context.

        Returns a dict with optional keys: `destination` (str, raw text),
        `search_area` (str, raw text), `start_date` / `end_date` (str, the
        caller parses), `duration` (int, days), `interests` (list[str]),
        `travel_style` (str), `pace` (str), `intent` (str). A key's absence
        means the message added or changed nothing for that field — never
        "clear it" (`TripContext.merge`'s own contract).

        Falls back to the deterministic heuristic only when the Gemini call
        itself fails — a *successful* call that extracts nothing (a plain
        "thanks!") is a valid, empty result and must not trigger the
        fallback, which would reintroduce exactly the fragile-regex-as-
        primary behaviour this architecture replaces.
        """
        try:
            return await self._llm_extract(current_context, history)
        except (
            LlmClientError,
            LlmTimeoutError,
            json.JSONDecodeError,
            _MalformedExtractionError,
        ) as exc:
            logger.warning("entity_extraction_failed_using_fallback", extra={"error": str(exc)})
            return self._fallback_heuristic_extract(message, current_context)

    def _build_extraction_prompt(
        self, current_context: TripContext, history: Sequence[Message], *, today: date
    ) -> str:
        """The structured-extraction prompt — history and current
        `TripContext` in, one JSON object out.

        Explicitly tells the model not to repeat an already-established
        destination and not to conflate `searchArea` with `destination` —
        the two ambiguities most likely to cause a wrong or wasted
        downstream geocoding call if left to chance.

        `today` is passed in (not read from the clock here) so a year-less
        date like "September 10" has something to resolve against — without
        it the model has no year to anchor to and silently drops the date
        rather than guess (see `_llm_extract`'s caller). The model's
        resolution is a best-effort read of the message, never trusted
        outright: whatever ISO date comes back still goes through the same
        `parse_iso_date` + `validate_trip_date_range` the rest of the
        pipeline already applies to every date, LLM-sourced or not.
        """
        history_text = _format_history(history)
        dest_display = (
            current_context.destination.display_name
            if current_context.destination
            else "not yet known"
        )
        dest_query = current_context.destination_query or "not yet known"
        start_date = current_context.start_date
        start = start_date.isoformat() if start_date else "not yet known"
        end = current_context.end_date.isoformat() if current_context.end_date else "not yet known"
        interests = (
            ", ".join(current_context.interests) if current_context.interests else "none yet"
        )
        travel_style = current_context.travel_style or "not yet known"
        pace = current_context.pace or "not yet known"
        # ISSUE-5 (E2E audit): the bare enum-name list alone left "which day
        # is best?" and "what places can I visit?" both landing on
        # `itinerary_request` — a label with no definition is ambiguous
        # between "asking about one day" and "asking for the whole trip's
        # schedule". Each value gets one disambiguating clause instead.
        intent_guide = (
            'trip_planning (establishing or changing the trip itself — '
            "destination, dates, interests, style, pace), "
            "itinerary_request (an explicit ask for a day-by-day plan or "
            "schedule across the WHOLE trip, e.g. \"plan out each day\"), "
            "weather_question (asking about conditions for a day or the whole "
            "trip, which day is best/worst, or safety/risk — e.g. \"which day "
            'is best?", "what if it rains?", "is it safe to travel", "any '
            'risks I should know about" — not a request for places), '
            "recommendation_request (asking what places, activities, food, "
            "or stays to visit or do), "
            "packing_request (what to bring or wear), "
            "general_chat (ONLY genuine small talk with no trip-planning "
            "content — thanks, greetings, chit-chat — never a real question "
            "about the trip's weather, safety, places, or plan, even a vague "
            'or broadly-phrased one)'
        )

        return (
            "You are the understanding layer of a conversational travel-planning "
            "assistant. Read the conversation and extract structured information "
            "from the LATEST user message as a single JSON object. Return ONLY the "
            "JSON object — no prose, no markdown fences.\n\n"
            f"Today's date is {today.isoformat()}.\n\n"
            f"CONVERSATION (the last line is the message to extract from):\n{history_text}\n\n"
            "TRIP CONTEXT ALREADY ESTABLISHED — do not repeat a value back unless "
            "the latest message actually changes it:\n"
            f'- destination: {dest_display} (as the user first wrote it: "{dest_query}")\n'
            f"- dates: {start} to {end}\n"
            f"- interests: {interests}\n"
            f"- travel style: {travel_style}\n"
            f"- pace: {pace}\n\n"
            "Use the conversation above to resolve references in the latest message "
            'such as "it", "there", "the second day", or an implied trip the message '
            "doesn't restate. Return a JSON object with any of these keys, omitting a "
            "key entirely when the latest message does not add or change that "
            "information:\n\n"
            "{\n"
            '  "destination": "raw place name, ONLY if this message introduces a NEW '
            'or CHANGED trip destination — never the one already established above",\n'
            '  "searchArea": "a specific place WITHIN or NEAR the trip destination the '
            "user is asking about for just this turn (e.g. \"more places near Kochi\") "
            '— never the main trip destination, never set together with destination",\n'
            '  "startDate": "YYYY-MM-DD — only an explicit or unambiguous calendar date",\n'
            '  "endDate": "YYYY-MM-DD — only an explicit or unambiguous calendar date",\n'
            '  "duration": integer number of days, whenever the message states a trip '
            "length (e.g. \"4-day trip\"), even alongside a startDate — give BOTH "
            "together when the message has a start date but not an end date (e.g. "
            "\"4-day trip starting Oct 1\" -> startDate AND duration, never just one); "
            "omit duration only if the message already gives an explicit endDate,\n"
            '  "interests": ["short words naming ONLY what the latest message itself '
            "asks for — a leisure theme (e.g. a place, activity, or food style) or a "
            "practical need (e.g. lodging, a sport) count equally, but every word here "
            'must trace to something the user actually wrote this turn"],\n'
            '  "travelStyle": "solo | couple | family | friends | business — inferred '
            'from who is travelling",\n'
            '  "pace": "short free-text pace preference, e.g. relaxed, packed, '
            'moderate",\n'
            f'  "intent": "exactly one of: {intent_guide}"\n'
            "}\n\n"
            "Rules:\n"
            "- Never invent a date, destination, or fact not present in the message or "
            "directly implied by it. If dates are not mentioned, omit startDate and "
            "endDate entirely — do not guess or default.\n"
            "- When the message gives a calendar date without a year (e.g. \"September "
            "10\" or \"the 10th to the 13th\"), resolve it against today's date above: "
            "use the current year, unless that month/day has already passed this year, "
            "in which case use next year instead — always the nearest such date on or "
            "after today. A date that already includes an explicit year is used as-is.\n"
            "- destination and searchArea never both appear on the same turn.\n"
            "- destination and searchArea must be an actual place name (a city, region, "
            "country, or landmark) — never a pronoun, article, or question word (\"can\", "
            "\"any\", \"what\", \"which\", \"there\", \"it\"). A question that happens to "
            "start with one of those words is not a destination mention; when in doubt, "
            "omit the field.\n"
            "- interests: only words the LATEST message itself introduces. A message "
            "that doesn't mention any interest (e.g. \"which day is best?\") must omit "
            "interests entirely — never repeat interests already established earlier in "
            "the conversation above; the caller keeps those, so repeating them back "
            "changes nothing and risks fabricating ones the latest message never said.\n"
            "- intent must be exactly one of the listed values, nothing else.\n"
            "- Output strictly the JSON object, nothing else."
        )

    async def _llm_extract(
        self,
        current_context: TripContext,
        history: Sequence[Message],
    ) -> dict[str, Any]:
        prompt = self._build_extraction_prompt(
            current_context, history, today=datetime.now(UTC).date()
        )
        raw_text = await self._llm_client.complete(
            system_prompt=prompt,
            user_content="Extract the structured request from the latest message above.",
            json_mode=True,
            temperature=_EXTRACTION_TEMPERATURE,
        )
        parsed = json.loads(raw_text.strip())
        if not isinstance(parsed, dict):
            raise _MalformedExtractionError(f"expected a JSON object, got {type(parsed).__name__}")

        return {
            _EXTRACTION_KEY_MAP[key]: value
            for key, value in parsed.items()
            if key in _EXTRACTION_KEY_MAP and value is not None
        }

    def _fallback_heuristic_extract(
        self, message: str, current_context: TripContext
    ) -> dict[str, Any]:
        """Deterministic, no-network extraction — used only when the Gemini
        extraction call itself failed. Never blended with a successful
        Gemini result."""
        msg_lower = message.lower()
        result: dict[str, Any] = {}

        if not current_context.destination and not current_context.destination_query:
            destination = self._extract_destination(message)
            if destination:
                result["destination"] = destination

        if not current_context.start_date:
            day_match = re.search(r"(\d+)\s*days?", msg_lower)
            if day_match:
                result["duration"] = int(day_match.group(1))

        search_area = self._extract_search_area_text(message)
        if search_area and "destination" not in result:
            result["search_area"] = search_area

        interest_keywords = {
            "beach": ["beach", "beaches", "coast", "shore", "sea", "ocean", "swim"],
            "food": ["food", "eat", "restaurant", "cuisine", "dining", "seafood", "local food"],
            "museum": ["museum", "museums", "art", "gallery", "history", "culture"],
            "nightlife": ["nightlife", "club", "bar", "party", "drink", "pub"],
            "hiking": ["hike", "hiking", "trail", "trek", "mountain", "walk"],
            "nature": ["nature", "park", "wildlife", "bird", "forest", "garden"],
            "shopping": ["shop", "shopping", "market", "mall", "boutique"],
            "photography": ["photo", "photography", "picture", "instagram", "shot"],
            "adventure": ["adventure", "thrill", "extreme", "zipline", "rafting"],
            "wellness": ["spa", "wellness", "yoga", "meditation", "relax", "massage"],
            "family": ["family", "kid", "children", "child", "family-friendly"],
            "luxury": ["luxury", "luxurious", "high-end", "premium", "5-star"],
            "budget": ["budget", "cheap", "affordable", "backpack", "hostel"],
        }
        found_interests = [
            interest
            for interest, keywords in interest_keywords.items()
            if any(kw in msg_lower for kw in keywords)
        ]
        if found_interests:
            result["interests"] = found_interests

        style_keywords = {
            "solo": ["solo", "alone", "by myself"],
            "couple": ["couple", "partner", "boyfriend", "girlfriend", "husband", "wife"],
            "family": ["family", "kids", "children"],
            "friends": ["friends", "group", "buddies"],
            "business": ["business", "work", "conference", "meeting"],
        }
        for style, keywords in style_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                result["travel_style"] = style

        return result

    def _extract_destination(self, message: str) -> str | None:
        """Capitalized-word heuristic, filtered against `_NON_DESTINATION_WORDS`.

        Position alone is not a reliable signal: "We are visiting Bali"
        capitalizes "We" for grammar, but "Goa, August 20 to 23" opens with
        a genuine destination — dropping whichever word comes first would
        fix one at the cost of breaking the other. The stopword list is the
        actual fix; a word is excluded because of *what it is*, never
        *where it sits*.

        Only a *contiguous run* of surviving candidates is ever joined into
        one destination — not just the first three found anywhere in the
        message. "New York" is one place because the two words sit right
        next to each other; "Kerala" and "India" in "Kerala in India" are
        not, because "in" — a real word, just not a capitalized one — sits
        between them. The previous version joined the first three
        candidates regardless of what separated them, which silently turned
        "Kerala in India" into the search query "Kerala India": ungeocodable
        (real bug, found live). A comma is still treated as the same run —
        "Kerala, India" is a standard disambiguating format, not a sentence
        break, and the geocoder's own ranking already expects a query shaped
        that way.
        """
        candidates = [
            match
            for match in re.finditer(r"\b[A-Z][a-z]+\b", message)
            if match.group().lower() not in self._NON_DESTINATION_WORDS
        ]
        if not candidates:
            return None

        best_run = current_run = [candidates[0]]
        for previous, current in zip(candidates, candidates[1:], strict=False):
            between = message[previous.end() : current.start()]
            current_run = [*current_run, current] if re.fullmatch(r"[\s,]*", between) else [current]
            if len(current_run) > len(best_run):
                best_run = current_run

        return " ".join(match.group() for match in best_run[:3])

    #: "near Panjim", "places in Calangute", "around Baga" — a sub-location
    #: mentioned in a follow-up, distinct from the trip destination itself.
    #: Deliberately separate from `_extract_destination`'s pattern (no
    #: preposition there) so a first-turn message ("trip to Goa") is never
    #: mistaken for a local-area query.
    _SEARCH_AREA_PATTERN = re.compile(
        r"\b(?:near|in|around)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})"
    )

    def _extract_search_area_text(self, message: str) -> str | None:
        """Extract a local sub-location the user wants to recenter on.

        "Give me more places near Panjim" -> "Panjim". Filtered against the
        same stopword set as destination extraction so "in August" (a date
        phrase, not a place) never matches — `_NON_DESTINATION_WORDS`
        already excludes every month name for exactly this reason. Fallback
        path only — Gemini's own `searchArea` field is the primary source.
        """
        match = self._SEARCH_AREA_PATTERN.search(message)
        if not match:
            return None
        words = [w for w in match.group(1).split() if w.lower() not in self._NON_DESTINATION_WORDS]
        return " ".join(words) if words else None


class ChatOrchestrator:
    """Main chat orchestration use case."""

    def __init__(
        self,
        *,
        conversation_repo: ConversationRepository,
        geocoding: GeocodingPort,
        intelligence_use_case: IntelligenceUseCase,
        attraction_provider: AttractionPort,
        llm_client: LlmClient,
        max_forecast_horizon_days: int,
    ) -> None:
        """No `NarrationPort` here, deliberately.

        `NarrationPort.narrate(intelligence, language) -> Narrative` is
        shaped for one job: restate a finished `WeatherIntelligence` object.
        A chat turn needs conversational history, attraction data, and the
        current question in the same call — a different shape entirely, not
        a variation of narration's. Reusing the port would mean either
        breaking its contract for every other caller (`/narrative` stays
        strict-503, per the approved chat-degrades/narrative-stays-strict
        split) or building a second, parallel LLM implementation next to it,
        which duplicates the exact thing this fix is supposed to prevent.
        The existing `LlmClient` transport is reused instead — same class,
        same retry/timeout policy, no second implementation — just called
        directly with a chat-shaped prompt instead of through the narration
        port's narrower signature.
        """
        self._conversation_repo = conversation_repo
        self._geocoding = geocoding
        self._intelligence_use_case = intelligence_use_case
        self._attraction_provider = attraction_provider
        self._llm_client = llm_client
        self._max_forecast_horizon_days = max_forecast_horizon_days
        self._entity_extractor = EntityExtractor(llm_client)

    async def process_message(
        self,
        *,
        conversation_id: UUID | None,
        user_message: str,
        user_id: str | None = None,
    ) -> ChatResult:
        """Process a user message and return the assistant response."""
        if conversation_id:
            conversation = await self._conversation_repo.get(conversation_id)
            if conversation is None:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = Conversation.start()

        conversation = conversation.add_user_message(user_message)
        was_complete_before_this_turn = conversation.trip_context.is_complete

        # A pending clarification takes priority over ordinary extraction:
        # if the previous turn asked "which Goa?", this message is most
        # likely an answer to that question, not a fresh trip description.
        pending_candidates = self._pending_candidates(conversation)
        selected_from_pending: GeocodedPlace | None = None
        carry_forward_candidates = False
        if pending_candidates and conversation.trip_context.destination is None:
            selected_from_pending = self._resolve_candidate_selection(
                user_message, pending_candidates
            )
            if selected_from_pending is None:
                # Unclear reply — keep the same options alive rather than
                # silently dropping them and re-asking a generic question.
                carry_forward_candidates = True

        history = conversation.messages[-_HISTORY_TURNS_IN_PROMPT:]
        extracted = await self._entity_extractor.extract(
            user_message, conversation.trip_context, history
        )

        destination = conversation.trip_context.destination
        destination_query = conversation.trip_context.destination_query
        destination_candidates: tuple[GeocodedPlace, ...] = ()

        extracted_destination = extracted.get("destination")
        if isinstance(extracted_destination, str):
            already_current = (
                conversation.trip_context.destination is not None
                and extracted_destination.strip().casefold()
                == (conversation.trip_context.destination_query or "").strip().casefold()
            )
            if already_current:
                # Gemini re-stated the destination that's already resolved
                # (models do this even when told not to) — treat as
                # "nothing new", not a fresh mention. Re-geocoding an
                # unchanged name risks a different candidate winning on a
                # second call and silently relocating an established trip.
                extracted_destination = None

        if selected_from_pending is not None:
            destination = selected_from_pending
            destination_query = selected_from_pending.name
        elif extracted_destination:
            carry_forward_candidates = False
            destination_query = extracted_destination
            try:
                candidates = await self._geocoding.search(destination_query)
            except Exception:
                candidates = []
                logger.warning("geocoding_failed", extra={"query": destination_query})
            if candidates:
                if _is_ambiguous_candidates(candidates, destination_query):
                    # Genuinely different places sharing a name (the classic
                    # case: Paris, France vs. Paris, Texas) — resolving
                    # silently risks planning the wrong trip entirely. Leave
                    # `destination` as it was and ask instead of guessing.
                    destination_candidates = tuple(candidates[:_MAX_CLARIFICATION_CANDIDATES])
                else:
                    destination = candidates[0]
        elif carry_forward_candidates:
            destination_candidates = pending_candidates

        new_context = conversation.trip_context.merge(
            destination=destination,
            destination_query=destination_query,
            start_date=parse_iso_date(extracted.get("start_date")),
            end_date=parse_iso_date(extracted.get("end_date")),
            interests=extracted.get("interests"),
            travel_style=extracted.get("travel_style"),
            pace=extracted.get("pace"),
        )
        if destination_candidates:
            # `merge(destination=None)` means "untouched", which is right
            # for every other `None` case but wrong here: a fresh ambiguous
            # mention must clear any *previously resolved* destination too —
            # the same override `dataclasses.replace` already applies below
            # for an invalid date range.
            new_context = replace(new_context, destination=None)

        # Backend normalization, not something Gemini is asked to compute:
        # a stated duration ("4-day trip") fills in the end date only when
        # a start date is known and no explicit end date was given.
        duration = extracted.get("duration")
        if (
            isinstance(duration, int)
            and not isinstance(duration, bool)
            and duration > 0
            and new_context.start_date is not None
            and new_context.end_date is None
        ):
            new_context = replace(
                new_context, end_date=new_context.start_date + timedelta(days=duration - 1)
            )

        # A bare single-day weather question ("will it rain in Mumbai
        # tomorrow?") gives a start date but never states a trip length —
        # unlike `trip_planning` wording, there's no "trip" being described
        # here to ask an end date *for*. Forcing the "when does your trip
        # end?" clarification onto a one-off forecast question is exactly
        # the kind of friction that makes the assistant feel like a form,
        # not a conversation, so a `weather_question` with only a start date
        # is read as asking about that single day, not opening a new trip.
        # `trip_planning` keeps asking, as it should: that wording usually
        # means more details (an end date, a duration) are still coming.
        if (
            extracted.get("intent") == "weather_question"
            and new_context.start_date is not None
            and new_context.end_date is None
        ):
            new_context = replace(new_context, end_date=new_context.start_date)

        # Same rule the HTTP layer enforces (`domain.rules.date_range`),
        # checked before any weather/provider I/O — a chat turn must not
        # reach a provider with a range REST already rejects at the door.
        date_range_error: InvalidDateRangeError | None = None
        if not new_context.missing_essentials():
            assert new_context.start_date is not None
            assert new_context.end_date is not None
            try:
                validate_trip_date_range(
                    new_context.start_date,
                    new_context.end_date,
                    max_horizon_days=self._max_forecast_horizon_days,
                    today=datetime.now(UTC).date(),
                )
            except InvalidDateRangeError as exc:
                date_range_error = exc
                # An invalid range must not be persisted as "known" dates —
                # otherwise the *next* turn's `was_complete_before_this_turn`
                # check would see a structurally complete (but factually
                # rejected) trip and jump straight to keyword classification
                # instead of still treating the trip as being established.
                # Clearing them here is what makes "ok, next month instead"
                # on the following turn correctly re-trigger the full
                # weather+attraction fetch once real dates arrive.
                new_context = replace(new_context, start_date=None, end_date=None)

        conversation = conversation.update_context(new_context)
        missing = new_context.missing_essentials()
        context_complete = not missing
        response_places: tuple[Attraction, ...] = ()

        if destination_candidates:
            # Checked first, same reasoning as `date_range_error` below:
            # destination is necessarily among `missing` here, but the
            # generic "where would you like to go?" clarification would
            # waste the geocoding work already done and lose the specific
            # options the user needs to answer with.
            response = self._generate_destination_clarification(
                destination_candidates, destination_query
            )
            intent = ChatIntent.TRIP_PLANNING
            llm_generated = False
        elif date_range_error is not None:
            # Checked ahead of `not context_complete` deliberately: all three
            # essentials WERE present (that's the only way this gets set) —
            # dates were cleared afterward specifically so the *next* turn
            # doesn't misread this trip as already complete. That clearing
            # must not demote this response to the generic "where/when"
            # clarification; the specific rejection reason is more useful and
            # still accurate. No weather/attraction I/O happens either way.
            response = self._generate_date_range_rejection(date_range_error, new_context)
            intent = ChatIntent.TRIP_PLANNING
            llm_generated = False
        elif not context_complete:
            response = self._generate_clarification(missing, new_context)
            intent = ChatIntent.TRIP_PLANNING
            llm_generated = False
        elif not was_complete_before_this_turn:
            # This turn is the one that completed the trip — always the full
            # answer, regardless of wording. Classifying by keyword here
            # would let "I'm planning a 4-day trip to Goa from August 20 to
            # August 23" land on GENERAL_CHAT (it contains none of the
            # recommendation/weather/itinerary keywords) and skip the very
            # weather+attraction fetch this message exists to trigger.
            # Keyword classification is for turns *after* a trip is already
            # established, not the turn that establishes it.
            intent = ChatIntent.TRIP_PLANNING
            search_area = await self._resolve_search_area(extracted, new_context.destination)
            response, llm_generated, response_places = await self._generate_travel_response(
                conversation,
                new_context,
                intent,
                user_message=user_message,
                search_area=search_area,
            )
        else:
            intent = self._resolve_intent(extracted.get("intent"), user_message, new_context)
            search_area = await self._resolve_search_area(extracted, new_context.destination)
            response, llm_generated, response_places = await self._generate_travel_response(
                conversation,
                new_context,
                intent,
                user_message=user_message,
                search_area=search_area,
            )

        conversation = conversation.add_assistant_message(
            response,
            metadata={
                "intent": intent.value,
                "llm_generated": llm_generated,
                **(
                    {"places": [_attraction_to_dict(p) for p in response_places]}
                    if response_places
                    else {}
                ),
                **(
                    {
                        "destination_candidates": [
                            _geocoded_place_to_dict(c) for c in destination_candidates
                        ]
                    }
                    if destination_candidates
                    else {}
                ),
            },
        )
        conversation = await self._conversation_repo.save(conversation)

        return ChatResult(
            conversation=conversation,
            response=response,
            context_complete=context_complete,
            missing_essentials=missing,
            intent=intent,
            llm_generated=llm_generated,
            places=response_places,
            destination_candidates=destination_candidates,
        )

    def _generate_clarification(self, missing: tuple[str, ...], context: TripContext) -> str:
        """Generate a natural clarifying question."""
        if MISSING_DESTINATION in missing:
            return "Where would you like to go? Please tell me the city or region."
        if MISSING_START_DATE in missing:
            dest = (
                context.destination.display_name
                if context.destination
                else context.destination_query or "your destination"
            )
            return f"Great! When does your trip to {dest} start? Please give me the start date."
        if MISSING_END_DATE in missing:
            return "When does your trip end? (Or how many days will you stay?)"
        return "I need a bit more information to help you plan. Could you tell me more?"

    def _generate_date_range_rejection(
        self, error: InvalidDateRangeError, context: TripContext
    ) -> str:
        """Conversational phrasing of the same rule `dependencies.validate_date_range`
        enforces for REST — same reason codes, different-shaped sentence."""
        dest = (
            context.destination.display_name
            if context.destination
            else context.destination_query or "your destination"
        )
        if error.reason == "end_before_start":
            return (
                f"Your end date needs to be on or after your start date for the trip to "
                f"{dest}. Could you give me the correct dates?"
            )
        if error.reason == "historical_range":
            return (
                f"I can only forecast upcoming weather, not dates that have already passed. "
                f"Could you give me upcoming dates for your trip to {dest}?"
            )
        if error.reason == "span_exceeds_horizon":
            return (
                f"That's a {error.span_days}-day trip, but I can only plan up to "
                f"{self._max_forecast_horizon_days} days at a time. Could you narrow the range?"
            )
        if error.reason == "beyond_horizon":
            return (
                f"Your end date is {error.days_ahead} days out, beyond the "
                f"{self._max_forecast_horizon_days}-day forecast window I can see. Could you "
                f"pick an earlier date range?"
            )
        return "Those dates don't work for a forecast — could you give me a different range?"

    def _pending_candidates(self, conversation: Conversation) -> tuple[GeocodedPlace, ...]:
        """Destination candidates a previous turn asked about, if any.

        Read from the last assistant message's `metadata` — the same place
        `intent`/`llm_generated` already live — never from `TripContext`,
        which only ever holds a *resolved* destination. A malformed or
        missing entry is treated as "no pending clarification", never a
        crash: this is best-effort continuity, not a contract other code
        depends on.
        """
        last = conversation.last_assistant_message
        if last is None:
            return ()
        raw = last.metadata.get("destination_candidates")
        if not isinstance(raw, list):
            return ()
        candidates: list[GeocodedPlace] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                candidates.append(
                    GeocodedPlace(
                        name=item["name"],
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                        country=item.get("country"),
                        country_code=item.get("country_code"),
                        admin1=item.get("admin1"),
                        timezone=item.get("timezone"),
                    )
                )
            except (KeyError, TypeError):
                continue
        return tuple(candidates)

    def _resolve_candidate_selection(
        self, message: str, candidates: tuple[GeocodedPlace, ...]
    ) -> GeocodedPlace | None:
        """Interpret a reply to a destination-clarification turn as a selection.

        Conservative on purpose: an unrecognized reply returns `None` and
        falls through to normal extraction (or a repeat of the same
        question) rather than guessing wrong — silently resolving to the
        wrong candidate is the one failure mode this feature exists to
        remove.
        """
        lowered = message.strip().lower()

        digit_match = re.fullmatch(r"\D*(\d+)\D*", lowered)
        if digit_match:
            index = int(digit_match.group(1)) - 1
            if 0 <= index < len(candidates):
                return candidates[index]

        for word, index in _ORDINAL_WORDS.items():
            if word in lowered and index < len(candidates):
                return candidates[index]

        text_matches = [
            candidate
            for candidate in candidates
            if (candidate.country and candidate.country.lower() in lowered)
            or (candidate.admin1 and candidate.admin1.lower() in lowered)
        ]
        if len(text_matches) == 1:
            return text_matches[0]

        return None

    def _generate_destination_clarification(
        self, candidates: tuple[GeocodedPlace, ...], query: str | None
    ) -> str:
        """Deterministic prose for an ambiguous destination.

        The structured options travel separately, on
        `ChatResult.destination_candidates` — this text is a human-readable
        companion, never the data source a frontend should parse.
        """
        name = query or "that place"
        lines = [f'I found more than one location named "{name}". Which one do you mean?']
        for index, candidate in enumerate(candidates, start=1):
            lines.append(f"{index}. {_clarification_label(candidate)}")
        lines.append("Reply with the number, or tell me which one you meant.")
        return "\n".join(lines)

    def _resolve_intent(
        self, raw_intent: object, message: str, context: TripContext
    ) -> ChatIntent:
        """Gemini's own contextual classification, with a deterministic
        guard: an unrecognized or missing value falls back to the keyword
        classifier rather than propagating a string this codebase has no
        handling for ("backend may still use deterministic guards for
        clearly invalid/unsafe states")."""
        if isinstance(raw_intent, str):
            try:
                return ChatIntent(raw_intent)
            except ValueError:
                logger.warning("unrecognized_intent_from_extraction", extra={"intent": raw_intent})
        return classify_intent(message, context)

    async def _resolve_search_area(
        self, extracted: dict[str, Any], trip_destination: GeocodedPlace | None
    ) -> GeocodedPlace | None:
        """Geocode the sub-location this turn named ("near Panjim"), if any.

        `search_area` comes from the same structured extraction as
        everything else this turn (Gemini's `searchArea` field, or the
        regex fallback's own `search_area` key when Gemini's call failed) —
        no second pass over the raw message. Returns a standalone
        `TripContext`-shaped place, never persisted and never merged into
        the conversation's real `TripContext` — the trip destination stays
        whatever it already was. `None` means no sub-location was named,
        which is the common case.

        Live-observed: the extraction prompt asks for a place "within or
        near" the trip destination, but nothing enforces that Gemini's
        output actually is one — one call extracted `searchArea: "that
        restaurant"` from "can you book me a table at that restaurant for
        dinner", and the geocoder's fuzzy match for that phrase returned a
        real but utterly unrelated place across the world. The backend
        guard the architecture keeps room for: any candidate implausibly far
        from the established trip destination is discarded rather than
        silently recentering the whole attraction search on the wrong
        country.
        """
        query = extracted.get("search_area")
        if not isinstance(query, str) or not query.strip():
            return None
        try:
            candidates = await self._geocoding.search(query)
        except Exception:
            logger.warning("search_area_geocoding_failed", extra={"query": query})
            return None
        if not candidates:
            return None
        candidate = candidates[0]
        if trip_destination is not None:
            distance_km = _haversine_km(
                trip_destination.latitude,
                trip_destination.longitude,
                candidate.latitude,
                candidate.longitude,
            )
            if distance_km > _MAX_SEARCH_AREA_DISTANCE_KM:
                logger.warning(
                    "search_area_implausibly_far",
                    extra={"query": query, "distance_km": round(distance_km)},
                )
                return None
        return candidate

    async def _generate_travel_response(
        self,
        conversation: Conversation,
        context: TripContext,
        intent: ChatIntent,
        *,
        user_message: str,
        search_area: GeocodedPlace | None = None,
    ) -> tuple[str, bool, tuple[Attraction, ...]]:
        """Fetch what `intent` needs, then generate the response.

        Intelligence is always fetched — cheap and cached by the time this
        runs (see below) — but `general_chat` and `packing_request` skip the
        attraction-provider call: no place lookup applies to either, and it's
        the one real per-turn cost in this method. Every other intent,
        `weather_question` included, fetches places too:
        a "what if it rains?" question is implicitly asking what to do about
        it, and the weather-aware ranking already surfaces indoor/good-
        weather options first on a poor-weather day — the places call is
        what makes that answer concrete instead of generic.

        `search_area`, if given, recenters only the attraction search — a
        local `.merge()`'d copy of `context`, never the context itself, so
        the persisted trip destination is untouched by a follow-up asking
        about a specific neighbourhood within the trip.
        """
        assert context.destination is not None
        assert context.start_date is not None
        assert context.end_date is not None

        # Fetched unconditionally, `general_chat` included: this method only
        # ever runs once the trip is already fully established (the asserts
        # above), so the fetch is already cheap and cached
        # (`CachedIntelligenceUseCase`) by the time any turn reaches here —
        # not the same cost tradeoff as the attraction-provider call below,
        # which does real per-turn work. Skipping it used to mean an
        # intent-classification miss (a real question the model mislabeled
        # general_chat — live-observed with "is it safe to travel each
        # day?") left the model with zero data and nothing to answer with,
        # producing the bare fallback stub instead of a real answer.
        intelligence_result = await self._intelligence_use_case.execute(
            latitude=context.destination.latitude,
            longitude=context.destination.longitude,
            start=context.start_date,
            end=context.end_date,
            name=context.destination.display_name,
        )
        intelligence = intelligence_result.intelligence
        attractions: AttractionRecommendation | None = None

        if intent not in (ChatIntent.GENERAL_CHAT, ChatIntent.PACKING_REQUEST):
            assert intelligence is not None
            preferred_types = self._interests_to_attraction_types(
                context.interests,
                message=user_message,
                intent=intent,
                broad_check_text=_recent_user_text(conversation),
            )
            attraction_context = (
                context.merge(destination=search_area) if search_area is not None else context
            )
            attractions = await self._attraction_provider.get_recommendations(
                trip_context=attraction_context,
                weather_intelligence=intelligence,
                preferred_types=preferred_types,
            )

        # An itinerary or recommendation ask is inherently a "give me the
        # spread" question — it shouldn't need the user to also say
        # "checklist" or "every day" to get more than a token place or two.
        wants_detail = _wants_detailed_response(user_message) or intent in (
            ChatIntent.ITINERARY_REQUEST,
            ChatIntent.RECOMMENDATION_REQUEST,
        )
        places_per_day = (
            _MAX_PLACES_PER_DAY_IN_RESPONSE if wants_detail else _PLACES_PER_DAY_IN_RESPONSE
        )

        response_text, llm_generated = await self._generate_conversational_narrative(
            conversation=conversation,
            context=context,
            intent=intent,
            intelligence=intelligence,
            attractions=attractions,
            search_area=search_area,
            wants_detail=wants_detail,
            places_per_day=places_per_day,
        )
        places = self._select_response_places(attractions, places_per_day=places_per_day)
        return response_text, llm_generated, places

    def _select_response_places(
        self, attractions: AttractionRecommendation | None, *, places_per_day: int
    ) -> tuple[Attraction, ...]:
        """The exact places this turn's reply is allowed to mention.

        Same per-day cap the prompt itself uses, flattened across days and
        deduplicated by id, in day order — so the structured `places` field
        returned to the caller can never contain a place absent from what
        the LLM was actually shown, or vice versa.
        """
        if attractions is None:
            return ()
        seen: set[str] = set()
        selected: list[Attraction] = []
        for day in attractions.daily:
            for attraction in day.attractions[:places_per_day]:
                if attraction.id not in seen:
                    seen.add(attraction.id)
                    selected.append(attraction)
        return tuple(selected)

    def _interests_to_attraction_types(
        self,
        interests: tuple[str, ...],
        *,
        message: str = "",
        intent: ChatIntent | None = None,
        broad_check_text: str = "",
    ) -> tuple[AttractionType, ...]:
        """Map user interests to attraction types.

        Also scans the raw turn `message` directly, not just the LLM's own
        `interests` extraction — live testing found the extraction step
        doesn't reliably echo back every interest word verbatim (observed:
        identical "find me a nice hotel" turns returned `interests: ['hotel']`
        on roughly 1 in 3 calls, ordinary LLM sampling variance, not a bug in
        the extraction prompt). A category the user explicitly named in this
        turn must not be missed just because that one call's extraction
        didn't surface it.

        Live-observed regression, a second instance of the same class of bug
        `_BROAD_ITINERARY_SPREAD` already exists for: `TripContext.interests`
        only ever accumulates, so a trip where the user mentioned "food" on
        turn one stayed food-only forever after — asking for "a detailed
        itinerary" later still only ever fetched restaurants, no viewpoints,
        monuments, or anything else, because `intent` never widened the
        category set on its own, only specific trigger phrases
        (`_wants_broad_itinerary`) did, and "itinerary" itself was never one
        of them. `itinerary_request` is inherently a "give me the whole day"
        ask, not a request for one category, so it now widens unconditionally
        — on top of, never instead of, whatever specific interests were
        actually named, so "an itinerary heavy on sports" still gets sports
        specifically as well as the broad spread.

        `broad_check_text`, when given, is checked instead of `message` for
        the broad-itinerary-phrase trigger specifically (`_recent_user_text`)
        — the exact-keyword interest scan below always stays scoped to this
        turn's own `message`, never blurred across turns.
        """
        mapping = {
            "beach": AttractionType.BEACH,
            "food": AttractionType.FOOD,
            "cafe": AttractionType.FOOD,
            "restaurant": AttractionType.RESTAURANT,
            "museum": AttractionType.MUSEUM,
            "nightlife": AttractionType.NIGHTLIFE,
            "hiking": AttractionType.HIKING,
            "nature": AttractionType.NATURE,
            "shopping": AttractionType.SHOPPING,
            "market": AttractionType.SHOPPING,
            "photography": AttractionType.PHOTOGRAPHY,
            "adventure": AttractionType.ADVENTURE,
            "wellness": AttractionType.WELLNESS,
            "family": AttractionType.FAMILY,
            "culture": AttractionType.CULTURAL_SITE,
            "monument": AttractionType.CULTURAL_SITE,
            "temple": AttractionType.CULTURAL_SITE,
            "gallery": AttractionType.CULTURAL_SITE,
            "landmark": AttractionType.LANDMARK,
            "attraction": AttractionType.LANDMARK,
            "sightseeing": AttractionType.LANDMARK,
            "viewpoint": AttractionType.VIEWPOINT,
            "view point": AttractionType.VIEWPOINT,
            "wildlife": AttractionType.WILDLIFE,
            "zoo": AttractionType.WILDLIFE,
            "water sports": AttractionType.WATER_SPORTS,
            "outdoor": AttractionType.OUTDOOR_ACTIVITY,
            "indoor": AttractionType.INDOOR_ACTIVITY,
            "hotel": AttractionType.HOTEL,
            "stay": AttractionType.HOTEL,
            "accommodation": AttractionType.HOTEL,
            "lodging": AttractionType.HOTEL,
            "guest house": AttractionType.GUEST_HOUSE,
            "hostel": AttractionType.GUEST_HOUSE,
            "sports": AttractionType.SPORTS_FACILITY,
            "tennis": AttractionType.SPORTS_FACILITY,
            "golf": AttractionType.SPORTS_FACILITY,
            "football": AttractionType.SPORTS_FACILITY,
            "cricket": AttractionType.SPORTS_FACILITY,
        }
        types = []
        haystacks = [interest.lower() for interest in interests]
        if message:
            haystacks.append(message.lower())
        for haystack in haystacks:
            for key, atype in mapping.items():
                if key in haystack:
                    types.append(atype)

        broad_text = broad_check_text or message
        wants_broad = bool(broad_text) and _wants_broad_itinerary(broad_text)
        if intent is ChatIntent.ITINERARY_REQUEST or wants_broad:
            types.extend(_BROAD_ITINERARY_SPREAD)

        seen: set[AttractionType] = set()
        deduped = []
        for atype in types:
            if atype not in seen:
                seen.add(atype)
                deduped.append(atype)
        return tuple(deduped)

    async def _generate_conversational_narrative(
        self,
        *,
        conversation: Conversation,
        context: TripContext,
        intent: ChatIntent,
        intelligence: WeatherIntelligence | None,
        attractions: AttractionRecommendation | None,
        search_area: GeocodedPlace | None = None,
        wants_detail: bool = False,
        places_per_day: int = _PLACES_PER_DAY_IN_RESPONSE,
    ) -> tuple[str, bool]:
        """Generate the response via the LLM; fall back to a structured
        summary only if the call itself fails (approved decision: chat
        degrades gracefully, unlike `/narrative`, which stays strict-503).

        Returns `(response_text, llm_generated)` so the caller — and tests —
        can tell the two paths apart without parsing prose.
        """
        prompt = self._build_conversational_prompt(
            conversation=conversation,
            context=context,
            intent=intent,
            intelligence=intelligence,
            wants_detail=wants_detail,
            places_per_day=places_per_day,
            attractions=attractions,
            search_area=search_area,
        )
        try:
            raw_text = await self._llm_client.complete(
                system_prompt=prompt, user_content="Respond now."
            )
        except (LlmClientError, LlmTimeoutError) as exc:
            logger.warning("chat_response_generation_failed", extra={"error": str(exc)})
            return self._fallback_response(context, intelligence, attractions), False

        text = raw_text.strip()
        if not text:
            logger.warning("chat_response_empty")
            return self._fallback_response(context, intelligence, attractions), False
        return text, True

    def _build_conversational_prompt(
        self,
        *,
        conversation: Conversation,
        context: TripContext,
        intent: ChatIntent,
        intelligence: WeatherIntelligence | None,
        attractions: AttractionRecommendation | None,
        search_area: GeocodedPlace | None = None,
        wants_detail: bool = False,
        places_per_day: int = _PLACES_PER_DAY_IN_RESPONSE,
    ) -> str:
        """Build the full prompt for the conversational response.

        Every fact in this prompt — weather numbers, place names, dates —
        came from a deterministic engine or a real provider before this
        function ever ran. The model is asked to narrate and never given
        room to introduce a fact that isn't already here (API Spec-style
        grounding, mirroring `narration.j2`'s discipline).
        """
        history_text = _format_history(conversation.messages[-_HISTORY_TURNS_IN_PROMPT:])

        dest = (
            context.destination.display_name
            if context.destination
            else context.destination_query or "your destination"
        )
        days = "?"
        if context.start_date and context.end_date:
            days = str((context.end_date - context.start_date).days + 1)
        interests_str = ", ".join(context.interests) if context.interests else "not specified"
        travel_style = context.travel_style or "not specified"
        pace = context.pace or "not specified"

        sections = [
            "You are a friendly, knowledgeable travel planner. "
            "Write a natural, conversational response.",
            "",
            f"CONVERSATION HISTORY:\n{history_text}",
            "",
            "TRIP CONTEXT:\n"
            f"- Destination: {dest}\n"
            f"- Dates: {context.start_date} to {context.end_date} ({days} days)\n"
            f"- Interests: {interests_str}\n"
            f"- Travel style: {travel_style}\n"
            f"- Preferred pace: {pace}",
        ]

        if intelligence is not None:
            trip_summary = intelligence.trip_summary
            best_days = ", ".join(d.isoformat() for d in trip_summary.best_days[:2])
            worst_days = ", ".join(d.isoformat() for d in trip_summary.worst_days[:2])
            packing_count = 10 if wants_detail else 5
            packing = ", ".join(trip_summary.overall_packing_list[:packing_count])
            timezone_name = context.destination.timezone if context.destination else None

            # Real per-day detail the deterministic engine already computes —
            # previously never reached this prompt at all, only the
            # trip-level rollup did. Without it, a live response reused the
            # single trip-level suitability score for every day in a table,
            # mislabeling it as if it varied day to day. UV/feels-like/
            # sunrise/sunset are the newly-fetched Open-Meteo fields; a
            # provider that lacks one just omits that clause, never guesses.
            daily_lines = []
            for day in intelligence.daily_intelligence:
                summary = day.summary
                parts = [
                    f"{day.date.strftime('%a %b %d')}: {summary.condition.value}, "
                    f"{summary.temp_min_c:.0f}-{summary.temp_max_c:.0f}°C"
                ]
                if summary.feels_like_max_c is not None:
                    parts.append(f"(feels up to {summary.feels_like_max_c:.0f}°C)")
                parts.append(f"{summary.precipitation_probability:.0%} rain")
                wind = f"wind {summary.wind_speed_kph:.0f} km/h"
                if summary.wind_gust_kph is not None:
                    wind += f" (gusts {summary.wind_gust_kph:.0f})"
                parts.append(wind)
                if summary.humidity is not None:
                    parts.append(f"humidity {summary.humidity:.0%}")
                if summary.uv_index_max is not None:
                    parts.append(
                        f"UV {summary.uv_index_max:.0f} ({_uv_category(summary.uv_index_max)})"
                    )
                sunrise = _local_clock_time(summary.sunrise, timezone_name)
                sunset = _local_clock_time(summary.sunset, timezone_name)
                if sunrise and sunset:
                    parts.append(f"sun {sunrise}–{sunset}")
                top_activity = max(
                    day.activity_suitability, key=lambda entry: entry.score, default=None
                )
                verdict = f"{day.risk_assessment.overall_risk_level} risk, {day.travel_advisory}"
                if top_activity is not None:
                    verdict += f", best for {top_activity.activity} ({top_activity.score}/100)"
                daily_lines.append(f"  {', '.join(parts)} — {verdict}")

            sections.append(
                "WEATHER INTELLIGENCE (already computed, real data — restate only, never "
                "alter or invent a number not shown here):\n"
                f"- Trip suitability score: {trip_summary.trip_suitability_score}/100\n"
                f"- Travel confidence: {trip_summary.travel_confidence:.0%}\n"
                f"- Best days: {best_days}\n"
                f"- Watch-out days: {worst_days}\n"
                f"- Overall risk: {trip_summary.overall_risk_level}\n"
                f"- Packing: {packing}\n"
                "- Day by day:\n" + "\n".join(daily_lines)
            )

        if attractions is not None:
            attr_lines = []
            for day_attr in attractions.daily:
                day_str = day_attr.date.strftime("%a %b %d")
                day_places = day_attr.attractions[:places_per_day]
                named = ", ".join(f"{a.name} ({a.type.value})" for a in day_places)
                attr_lines.append(f"  {day_str}: {named}")
            area_note = (
                f" — the user asked specifically about {search_area.display_name}, "
                f"so these are centered there rather than on {dest} generally"
                if search_area is not None
                else ""
            )
            sections.append(
                f"DAILY ATTRACTIONS (real places from the places provider, with their "
                f"type in parentheses{area_note} — never invent a name not listed here, "
                "and only slot a place into breakfast/lunch/dinner if its type is "
                "restaurant, cafe, or food — a museum, landmark, or other non-food type "
                "is a thing to do, never a meal stop):\n" + "\n".join(attr_lines)
            )

        shape = _INTENT_RESPONSE_SHAPES.get(
            intent, _INTENT_RESPONSE_SHAPES[ChatIntent.GENERAL_CHAT]
        )
        always_rules = (
            "- Talk like a well-traveled friend giving advice over text, not a formal "
            "report — warm and casual, the way you'd naturally reply to someone. "
            "Contractions are fine, a little personality is fine, an exclamation point here "
            "and there is fine. Skip pure filler that adds nothing ('Great question!', "
            "'I'd be happy to help!'), but a natural, friendly opening is welcome — you "
            "don't need to open with the bare fact like a database dump.\n"
            "- Places, packing items, and weather/trip numbers must only ever be ones that "
            "actually appear above — never invent or add one of your own, even a small, "
            "plausible-sounding extra like a spare packing item. If something specific "
            "wasn't provided, say so plainly in passing — but never refuse or apologize "
            "when the data above already answers the question; declining when the answer "
            "is right there is worse than a short one. General travel knowledge about the "
            "destination itself (well-known local dishes, what a region is famous for) is "
            "fine to mention as color, since that's common knowledge about the place, not "
            "a claim about specific computed data — but keep it general to the destination, "
            "never attributed to one of the specific real venues above. You have no menu, "
            "hours, or review data for any listed place, so never say what a named "
            "restaurant serves, claim a specific dish is 'their specialty' or 'a must-try "
            "there', or invent why a specific place is good beyond its type and what's "
            "generally nearby.\n"
            "- When you mention a place, give it a little life — what its type suggests "
            "about the experience (a museum is browsing exhibits, a cafe is a relaxed "
            "sit-down), how it fits the day's weather, roughly where it falls in the day "
            "— the way you'd tip off a friend, not just recite a name from a list. This is "
            "color about the kind of place it is, never invented specifics about that one "
            "venue (no menu items, no 'their famous X', no made-up backstory).\n"
            f"- Match the answer to what was asked: {shape}"
        )
        if wants_detail:
            # The user explicitly asked for a checklist, a full itinerary, or
            # "every day" (or the intent itself already implies wanting a
            # full spread — itinerary/recommendation asks, not just a quick
            # answer). Live-observed: forcing a packing "checklist" ask into
            # 3 sentences with no lists produced an outright refusal, and a
            # "3 restaurants a day" ask stayed capped at one place total.
            sections.append(
                "RESPONSE GUIDELINES:\n" + always_rules + "\n"
                "- Give the full picture — every real place above that's relevant, with a "
                "bit of color on each (what it's known for, what's nearby, why it fits). "
                "Length should match what a genuinely useful answer needs, not be padded "
                "or clipped short.\n"
                "- A markdown list (one item, or one day, per line) works well for a "
                "checklist or a day-by-day plan — use it when it makes the answer easier "
                "to follow. For an actual packing checklist specifically, use task-list "
                "syntax (`- [ ] item`) instead of a plain bullet — it renders as a real "
                "checkbox. A markdown table is the clearest shape for a day-by-day "
                "itinerary with more than one column of information (e.g. time, place, "
                "why it fits). A short `> ` blockquote line works well for one standout "
                "tip or watch-out you want to set apart from the rest of the answer — use "
                "it sparingly, not for every sentence.\n"
                "- Still never invent an item, place or fact not listed above."
            )
        else:
            sections.append(
                "RESPONSE GUIDELINES:\n" + always_rules + "\n"
                "- Write however long feels natural for a real answer — often a short "
                "paragraph, sometimes just a sentence or two if that's genuinely all it "
                "takes. Don't pad it out with a closing well-wish or an offer to help "
                "further, but don't clip it into a robotic fragment either.\n"
                "- Do not restate the trip's score, confidence, best/watch-out days, full "
                "packing list or day-by-day breakdown unless the user asked for that "
                "specific thing — the interface already shows all of it beside your reply, "
                "and repeating it is noise.\n"
                "- A couple of places is usually plenty here — save the full rundown for "
                "when they ask for one."
            )

        return "\n\n".join(sections)

    def _fallback_response(
        self,
        context: TripContext,
        intelligence: WeatherIntelligence | None,
        attractions: AttractionRecommendation | None,
    ) -> str:
        """Structured fallback when the LLM call fails or returns nothing."""
        dest = (
            context.destination.display_name
            if context.destination
            else context.destination_query or "your destination"
        )
        lines = [f"Your trip to {dest} is taking shape!", ""]

        if intelligence:
            ts = intelligence.trip_summary
            lines.append(
                f"Trip suitability: {ts.trip_suitability_score}/100 "
                f"({ts.overall_risk_level} risk)"
            )
            if ts.best_days:
                best = ", ".join(d.isoformat() for d in ts.best_days[:2])
                lines.append(f"Best days: {best}")
            if ts.worst_days:
                worst = ", ".join(d.isoformat() for d in ts.worst_days[:2])
                lines.append(f"Watch out for: {worst}")
            if ts.overall_packing_list:
                lines.append(f"Packing: {', '.join(ts.overall_packing_list[:5])}")
            lines.append("")

        if attractions:
            for day_attr in attractions.daily[:3]:
                day_str = day_attr.date.strftime("%a %b %d")
                day_places = day_attr.attractions[:_PLACES_PER_DAY_IN_RESPONSE]
                names = ", ".join(a.name for a in day_places)
                if names:
                    lines.append(f"{day_str}: {names}")
            lines.append("")

        lines.append("Let me know if you'd like more details!")
        return "\n".join(lines).strip()
