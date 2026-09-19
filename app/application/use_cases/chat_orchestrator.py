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

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

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

#: Turns kept in the prompt's conversation-history section. Bounded so a long
#: conversation doesn't grow the prompt (and therefore cost/latency)
#: unboundedly — recent context matters far more than early context once a
#: trip's essentials are already captured in `TripContext`.
_HISTORY_TURNS_IN_PROMPT = 6

#: Places referenced per day when building the LLM prompt AND when
#: populating the structured `places` field on the response — one shared
#: cap so the two can never drift apart: the reply can't mention a place
#: absent from the structured list, and vice versa.
_PLACES_PER_DAY_IN_RESPONSE = 3

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


def _is_ambiguous_candidates(candidates: list[GeocodedPlace]) -> bool:
    """True when the top geocoding candidates plausibly name different places.

    Deliberately narrow: candidates that share one country are treated as
    the same place ranked several ways (duplicate gazetteer entries,
    districts of one city) and resolved automatically, exactly as before
    this feature existed. Candidates split across more than one country are
    the case a fuzzy, population-ranked geocoder actually gets wrong for a
    chat assistant — a bare "Paris" resolving to Paris, France vs. Paris,
    Texas — and that is what gets asked about, not every multi-result query.
    """
    if len(candidates) < 2:
        return False
    identities = {candidate.country_code or candidate.country for candidate in candidates}
    return len(identities) > 1


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
        "state the trip's headline verdict in one sentence and the single thing that most "
        "shapes it in another — the outlook, days and packing are already on screen beside "
        "you, so do not walk through them"
    ),
    ChatIntent.ITINERARY_REQUEST: (
        "one short line per day, no preamble before the first day and nothing after the last"
    ),
    ChatIntent.WEATHER_QUESTION: (
        "name the day and its condition, then what to do about it — two sentences total"
    ),
    ChatIntent.RECOMMENDATION_REQUEST: (
        "name the places and who each suits, nothing else; if none were provided, say in one "
        "full sentence that you have no places for this destination yet and suggest what the "
        "weather makes sensible instead — never answer with a bare word like 'None'"
    ),
    ChatIntent.PACKING_REQUEST: (
        "the items as one comma-separated run, plus at most one clause on why the weather "
        "calls for them"
    ),
    ChatIntent.GENERAL_CHAT: "one or two sentences",
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
        intent_values = ", ".join(f'"{value.value}"' for value in ChatIntent)

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
            '  "duration": integer number of days, only if the message states a trip '
            "length (e.g. \"4-day trip\") and does not already give both dates,\n"
            '  "interests": ["short interest words actually mentioned, e.g. nature, '
            'food, beaches"],\n'
            '  "travelStyle": "solo | couple | family | friends | business — inferred '
            'from who is travelling",\n'
            '  "pace": "short free-text pace preference, e.g. relaxed, packed, '
            'moderate",\n'
            f'  "intent": "exactly one of: {intent_values}"\n'
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
                if _is_ambiguous_candidates(candidates):
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
            search_area = await self._resolve_search_area(extracted)
            response, llm_generated, response_places = await self._generate_travel_response(
                conversation, new_context, intent, search_area=search_area
            )
        else:
            intent = self._resolve_intent(extracted.get("intent"), user_message, new_context)
            search_area = await self._resolve_search_area(extracted)
            response, llm_generated, response_places = await self._generate_travel_response(
                conversation, new_context, intent, search_area=search_area
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
            lines.append(f"{index}. {candidate.display_name}")
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

    async def _resolve_search_area(self, extracted: dict[str, Any]) -> GeocodedPlace | None:
        """Geocode the sub-location this turn named ("near Panjim"), if any.

        `search_area` comes from the same structured extraction as
        everything else this turn (Gemini's `searchArea` field, or the
        regex fallback's own `search_area` key when Gemini's call failed) —
        no second pass over the raw message. Returns a standalone
        `TripContext`-shaped place, never persisted and never merged into
        the conversation's real `TripContext` — the trip destination stays
        whatever it already was. `None` means no sub-location was named,
        which is the common case.
        """
        query = extracted.get("search_area")
        if not isinstance(query, str) or not query.strip():
            return None
        try:
            candidates = await self._geocoding.search(query)
        except Exception:
            logger.warning("search_area_geocoding_failed", extra={"query": query})
            return None
        return candidates[0] if candidates else None

    async def _generate_travel_response(
        self,
        conversation: Conversation,
        context: TripContext,
        intent: ChatIntent,
        *,
        search_area: GeocodedPlace | None = None,
    ) -> tuple[str, bool, tuple[Attraction, ...]]:
        """Fetch what `intent` needs, then generate the response.

        `general_chat` skips both weather and attraction fetches entirely.
        `packing_request` fetches intelligence only — the packing list it
        needs is already part of that result, and no place lookup applies.
        Every other intent, `weather_question` included, fetches places too:
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

        intelligence: WeatherIntelligence | None = None
        attractions: AttractionRecommendation | None = None

        if intent is not ChatIntent.GENERAL_CHAT:
            intelligence_result = await self._intelligence_use_case.execute(
                latitude=context.destination.latitude,
                longitude=context.destination.longitude,
                start=context.start_date,
                end=context.end_date,
                name=context.destination.display_name,
            )
            intelligence = intelligence_result.intelligence

        if intent not in (ChatIntent.GENERAL_CHAT, ChatIntent.PACKING_REQUEST):
            assert intelligence is not None
            preferred_types = self._interests_to_attraction_types(context.interests)
            attraction_context = (
                context.merge(destination=search_area) if search_area is not None else context
            )
            attractions = await self._attraction_provider.get_recommendations(
                trip_context=attraction_context,
                weather_intelligence=intelligence,
                preferred_types=preferred_types,
            )

        response_text, llm_generated = await self._generate_conversational_narrative(
            conversation=conversation,
            context=context,
            intent=intent,
            intelligence=intelligence,
            attractions=attractions,
            search_area=search_area,
        )
        return response_text, llm_generated, self._select_response_places(attractions)

    def _select_response_places(
        self, attractions: AttractionRecommendation | None
    ) -> tuple[Attraction, ...]:
        """The exact places this turn's reply is allowed to mention.

        Same per-day cap the prompt itself uses (`_PLACES_PER_DAY_IN_RESPONSE`),
        flattened across days and deduplicated by id, in day order — so the
        structured `places` field returned to the caller can never contain a
        place absent from what Gemini was actually shown, or vice versa.
        """
        if attractions is None:
            return ()
        seen: set[str] = set()
        selected: list[Attraction] = []
        for day in attractions.daily:
            for attraction in day.attractions[:_PLACES_PER_DAY_IN_RESPONSE]:
                if attraction.id not in seen:
                    seen.add(attraction.id)
                    selected.append(attraction)
        return tuple(selected)

    def _interests_to_attraction_types(
        self, interests: tuple[str, ...]
    ) -> tuple[AttractionType, ...]:
        """Map user interests to attraction types."""
        mapping = {
            "beach": AttractionType.BEACH,
            "food": AttractionType.FOOD,
            "museum": AttractionType.MUSEUM,
            "nightlife": AttractionType.NIGHTLIFE,
            "hiking": AttractionType.HIKING,
            "nature": AttractionType.NATURE,
            "shopping": AttractionType.SHOPPING,
            "photography": AttractionType.PHOTOGRAPHY,
            "adventure": AttractionType.ADVENTURE,
            "wellness": AttractionType.WELLNESS,
            "family": AttractionType.FAMILY,
            "culture": AttractionType.CULTURAL_SITE,
            "landmark": AttractionType.LANDMARK,
            "water sports": AttractionType.WATER_SPORTS,
            "outdoor": AttractionType.OUTDOOR_ACTIVITY,
            "indoor": AttractionType.INDOOR_ACTIVITY,
        }
        types = []
        for interest in interests:
            for key, atype in mapping.items():
                if key in interest.lower():
                    types.append(atype)
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
            packing = ", ".join(trip_summary.overall_packing_list[:5])
            sections.append(
                "WEATHER INTELLIGENCE (already computed — restate only, never alter):\n"
                f"- Trip suitability score: {trip_summary.trip_suitability_score}/100\n"
                f"- Travel confidence: {trip_summary.travel_confidence:.0%}\n"
                f"- Best days: {best_days}\n"
                f"- Watch-out days: {worst_days}\n"
                f"- Overall risk: {trip_summary.overall_risk_level}\n"
                f"- Packing: {packing}"
            )

        if attractions is not None:
            attr_lines = []
            for day_attr in attractions.daily:
                day_str = day_attr.date.strftime("%a %b %d")
                day_places = day_attr.attractions[:_PLACES_PER_DAY_IN_RESPONSE]
                names = ", ".join(a.name for a in day_places)
                attr_lines.append(f"  {day_str}: {names}")
            area_note = (
                f" — the user asked specifically about {search_area.display_name}, "
                f"so these are centered there rather than on {dest} generally"
                if search_area is not None
                else ""
            )
            sections.append(
                f"DAILY ATTRACTIONS (real places from the places provider{area_note} — "
                "never invent a name not listed here):\n" + "\n".join(attr_lines)
            )

        shape = _INTENT_RESPONSE_SHAPES.get(
            intent, _INTENT_RESPONSE_SHAPES[ChatIntent.GENERAL_CHAT]
        )
        sections.append(
            "RESPONSE GUIDELINES:\n"
            "- Open with the answer itself. The first word must be part of the answer — "
            "never a greeting, never the user's name for what they asked. Banned openings: "
            "'Hey', 'Hi', 'Great question', 'Sure', 'Absolutely', 'Let me', 'I'd be happy "
            "to', 'Your trip is shaping up'.\n"
            "- Hard limit: 3 sentences. Most answers need two. Stop at the answer; do not "
            "add a closing thought, a well-wish or an offer to help further.\n"
            "- Do not restate the trip's score, confidence, best/watch-out days, full "
            "packing list or day-by-day breakdown unless the user asked for that specific "
            "thing — the interface already shows all of it beside your reply, and "
            "repeating it is noise.\n"
            "- Name at most two or three places, and only ones listed above.\n"
            "- Only mention attractions and weather facts that appear above — never invent "
            "one. If something was not provided, say so plainly in one clause.\n"
            "- Give a reason only when it changes what the user would do, in the same "
            "sentence rather than a separate paragraph.\n"
            "- Professional and direct, like a planner who respects the reader's time. "
            "No recap of the question, no sign-off, no exclamation marks.\n"
            f"- Match the answer to what was asked: {shape}\n"
            "- Do NOT output JSON, markdown headings or bullet lists — just natural text"
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
            lines.append(f"Trip suitability: {ts.trip_suitability_score}/100")
            best = ", ".join(d.isoformat() for d in ts.best_days[:2])
            lines.append(f"Best days: {best}")
            packing = ", ".join(ts.overall_packing_list[:5])
            lines.append(f"Packing: {packing}")
            lines.append("")

        if attractions:
            for day_attr in attractions.daily[:3]:
                day_str = day_attr.date.strftime("%a %b %d")
                day_places = day_attr.attractions[:_PLACES_PER_DAY_IN_RESPONSE]
                names = ", ".join(a.name for a in day_places)
                lines.append(f"{day_str}: {names}")

        lines.append("\nLet me know if you'd like more details!")
        return "\n".join(lines)
