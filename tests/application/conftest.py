"""Shared fakes for `ChatOrchestrator` tests — no network, no database.

Every fake implements the exact port/class surface `ChatOrchestrator` calls,
scripted per test rather than mocked generically, so a test reads as "given
this response, expect this behaviour" rather than asserting on call counts
alone.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

import pytest

from app.domain.entities.attractions import (
    Attraction,
    AttractionRecommendation,
    AttractionType,
    DailyAttractions,
    WeatherSuitability,
)
from app.domain.entities.conversation import Conversation, Message
from app.domain.entities.trip import GeocodedPlace
from app.domain.entities.weather_intelligence import (
    Period,
    ResolvedLocation,
    WeatherIntelligence,
    build_weather_intelligence,
)
from app.domain.ports.attractions import AttractionPort
from app.domain.ports.conversation import ConversationRepository
from app.domain.ports.geocoding import GeocodingPort
from app.domain.rules.config import parse_rule_config

GOA = GeocodedPlace(
    name="Goa", latitude=15.2993, longitude=74.1240, country="India", country_code="IN"
)
BALI = GeocodedPlace(name="Bali", latitude=-8.4095, longitude=115.1889, country="Indonesia")
PANJIM = GeocodedPlace(name="Panjim", latitude=15.4909, longitude=73.8278, country="India")
CALANGUTE = GeocodedPlace(name="Calangute", latitude=15.5439, longitude=73.7553, country="India")
PARIS_FRANCE = GeocodedPlace(
    name="Paris", latitude=48.8566, longitude=2.3522, country="France", country_code="FR"
)
PARIS_TEXAS = GeocodedPlace(
    name="Paris",
    latitude=33.6609,
    longitude=-95.5555,
    country="United States",
    country_code="US",
    admin1="Texas",
)
SPRINGFIELD_MISSOURI = GeocodedPlace(
    name="Springfield",
    latitude=37.2090,
    longitude=-93.2923,
    country="United States",
    country_code="US",
    admin1="Missouri",
)
KERALA = GeocodedPlace(
    name="Kerala", latitude=10.8505, longitude=76.2711, country="India", country_code="IN"
)
KOCHI = GeocodedPlace(
    name="Kochi", latitude=9.9312, longitude=76.2673, country="India", country_code="IN"
)
BANGALORE = GeocodedPlace(
    name="Bangalore", latitude=12.97194, longitude=77.59369, country="India", country_code="IN"
)


def make_attraction_recommendation(
    *, start: date, end: date, location_id: str = f"{GOA.latitude},{GOA.longitude}"
) -> AttractionRecommendation:
    """A real, small `AttractionRecommendation` — two named places per day,
    one repeated on both days, to exercise both the per-day cap and the
    across-day dedup `ChatOrchestrator._select_response_places` applies."""
    beach = Attraction(
        id="node/1",
        name="Baga Beach",
        type=AttractionType.BEACH,
        description="Baga Beach, a beach.",
        latitude=15.5553,
        longitude=73.7517,
        weather_suitability=WeatherSuitability.IDEAL,
        weather_notes="Clear, 24-31C, 10% chance of rain (suitability 90/100).",
    )
    museum = Attraction(
        id="node/2",
        name="Museum of Christian Art",
        type=AttractionType.MUSEUM,
        description="Museum of Christian Art, a museum.",
        latitude=15.4989,
        longitude=73.8278,
        address="Rua de Ourem, Goa",
        weather_suitability=WeatherSuitability.GOOD,
        weather_notes="Clear, 24-31C, 10% chance of rain (suitability 65/100).",
    )
    days = (end - start).days + 1
    daily = tuple(
        DailyAttractions(
            date=date.fromordinal(start.toordinal() + offset),
            location_id=location_id,
            attractions=(beach, museum),
        )
        for offset in range(days)
    )
    return AttractionRecommendation(
        location_id=location_id, period_start=start, period_end=end, daily=daily
    )

_RULE_CONFIG_DATA: dict[str, Any] = {
    "version": "test-2026.07",
    "insight_thresholds": {
        "heat": {"moderate_temp_max_c": 30.0, "high_temp_max_c": 35.0},
        "cold": {"moderate_temp_min_c": 10.0, "high_temp_min_c": 5.0},
        "rain": {"moderate_precip_probability": 0.6, "high_precip_probability": 0.8},
        "wind": {"moderate_wind_speed_kph": 25.0, "high_wind_speed_kph": 40.0},
    },
    "activity_scoring": {
        "outdoor_sightseeing": {"base_score": 80, "penalties": {"rain": 30}, "bonuses": {}},
        "beach": {"base_score": 70, "penalties": {"rain": 40}, "bonuses": {"heat": 10}},
        "indoor_museum": {"base_score": 60, "penalties": {}, "bonuses": {"rain": 20}},
    },
    "packing_rules": {"rain": ["waterproof jacket"], "heat": ["sunscreen"]},
    "packing_item_order": ["waterproof jacket", "sunscreen"],
    "confidence": {
        "horizon_weight": 0.4,
        "agreement_weight": 0.2,
        "completeness_weight": 0.4,
        "max_horizon_days": 16,
        "single_provider_neutral_factor": 0.8,
    },
}


def make_intelligence(*, start: date, end: date) -> WeatherIntelligence:
    """A real, small `WeatherIntelligence` — enough days for the range, all clear."""
    from app.domain.entities.weather import NormalizedReading, WeatherCondition

    days = (end - start).days + 1
    readings = [
        NormalizedReading(
            date=date.fromordinal(start.toordinal() + offset),
            temp_min_c=20.0,
            temp_max_c=27.0,
            precipitation_probability=0.1,
            wind_speed_kph=10.0,
            condition=WeatherCondition.CLEAR,
            completeness=1.0,
            source_class="forecast",
        )
        for offset in range(days)
    ]
    return build_weather_intelligence(
        location=ResolvedLocation(
            id=f"{GOA.latitude},{GOA.longitude}", latitude=GOA.latitude, longitude=GOA.longitude
        ),
        period=Period(start_date=start, end_date=end),
        readings=readings,
        rule_config=parse_rule_config(_RULE_CONFIG_DATA),
        as_of=start,
    )


@dataclass(frozen=True, slots=True)
class _FakeIntelligenceResult:
    intelligence: WeatherIntelligence


class FakeIntelligenceUseCase:
    """Stands in for `GetWeatherIntelligence` — no provider, no database.

    Satisfies `cached_intelligence.IntelligenceUseCase` structurally
    (`rule_config_version` included) — `CachedIntelligenceUseCase` reads it
    for its cache key even when wrapping a fake, and API-level tests exercise
    exactly that wrapping since they override at the `WeatherIntelligenceUseCaseDep`
    seam, one layer below where the chat-only cache wrapper sits.
    """

    def __init__(self) -> None:
        self.call_count = 0
        self.last_call: dict[str, Any] | None = None
        self.rule_config_version = "test-2026.07"

    async def execute(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> _FakeIntelligenceResult:
        self.call_count += 1
        self.last_call = {
            "latitude": latitude, "longitude": longitude, "start": start, "end": end, "name": name,
        }
        return _FakeIntelligenceResult(intelligence=make_intelligence(start=start, end=end))


class FakeGeocoding(GeocodingPort):
    """Scriptable `GeocodingPort`."""

    def __init__(
        self,
        *,
        results: dict[str, list[GeocodedPlace]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._results = results or {}
        self._error = error
        self.queries: list[str] = []

    async def search(self, query: str, *, limit: int = 5) -> list[GeocodedPlace]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        for key, places in self._results.items():
            if key.lower() in query.lower():
                return places
        return []


class FakeAttractionProvider(AttractionPort):
    """Scriptable `AttractionPort` — never called unless the intent needs it."""

    def __init__(self, *, recommendation: AttractionRecommendation | None = None) -> None:
        self.call_count = 0
        #: The `trip_context` each call actually received, in order — used
        #: to assert a search-area override recentered the search without
        #: touching the conversation's real, persisted destination.
        self.calls_trip_context: list = []
        #: When set, returned verbatim regardless of the call's own
        #: `weather_intelligence` — lets a test script real `Attraction`s to
        #: assert on `ChatResult.places` without a real `PlacesPort`.
        self._recommendation = recommendation

    async def get_recommendations(
        self, *, trip_context, weather_intelligence, preferred_types=()
    ) -> AttractionRecommendation:
        self.call_count += 1
        self.calls_trip_context.append(trip_context)
        if self._recommendation is not None:
            return self._recommendation
        return AttractionRecommendation(
            location_id=weather_intelligence.location.id,
            period_start=weather_intelligence.period.start_date,
            period_end=weather_intelligence.period.end_date,
            daily=(),
        )


class FakeConversationRepository(ConversationRepository):
    """In-memory `ConversationRepository`."""

    def __init__(self) -> None:
        self._store: dict[UUID, Conversation] = {}
        self.save_count = 0

    async def get(self, conversation_id: UUID) -> Conversation | None:
        return self._store.get(conversation_id)

    async def save(self, conversation: Conversation) -> Conversation:
        self.save_count += 1
        self._store[conversation.id] = conversation
        return conversation

    async def get_active_for_user(self, user_id: str | None = None) -> list[Conversation]:
        return [c for c in self._store.values() if c.is_active]

    async def get_messages(
        self, conversation_id: UUID, *, limit: int | None = None, offset: int = 0, before=None
    ) -> list[Message]:
        conversation = self._store.get(conversation_id)
        if conversation is None:
            return []
        messages = list(reversed(conversation.messages))
        if before is not None:
            messages = [m for m in messages if m.created_at < before]
        messages = messages[offset:]
        return messages[:limit] if limit else messages

    async def delete(self, conversation_id: UUID) -> bool:
        return self._store.pop(conversation_id, None) is not None


@dataclass
class FakeLlmClient:
    """Scriptable `LlmClient` stand-in.

    Distinguishes an entity-extraction call from a chat-response call by
    prompt content — `EntityExtractor` and `ChatOrchestrator` share one
    client instance in production, so a realistic fake must too.
    """

    extraction_response: str = "{}"
    chat_response: str = "Sounds like a wonderful trip! Pack light and enjoy the sunshine."
    raise_on_extraction: Exception | None = None
    raise_on_chat: Exception | None = None
    calls: list[tuple[str, str, bool, float | None]] = field(default_factory=list)

    @property
    def model(self) -> str:
        return "fake-model"

    async def complete(
        self,
        *,
        system_prompt: str,
        user_content: str,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        # `json_mode` is exactly how the real orchestrator distinguishes the
        # two calls (extraction always passes it; response generation never
        # does) — matching on that instead of prompt text means this fake
        # never goes stale when the prompt wording changes.
        self.calls.append((system_prompt, user_content, json_mode, temperature))
        if json_mode:
            if self.raise_on_extraction is not None:
                raise self.raise_on_extraction
            return self.extraction_response
        if self.raise_on_chat is not None:
            raise self.raise_on_chat
        return self.chat_response

    @property
    def extraction_call_count(self) -> int:
        return sum(1 for _, _, json_mode, _ in self.calls if json_mode)

    @property
    def chat_call_count(self) -> int:
        return sum(1 for _, _, json_mode, _ in self.calls if not json_mode)


@pytest.fixture
def conversation_repo() -> FakeConversationRepository:
    return FakeConversationRepository()


@pytest.fixture
def geocoding() -> FakeGeocoding:
    return FakeGeocoding(results={"goa": [GOA], "bali": [BALI]})


@pytest.fixture
def intelligence_use_case() -> FakeIntelligenceUseCase:
    return FakeIntelligenceUseCase()


@pytest.fixture
def attraction_provider() -> FakeAttractionProvider:
    return FakeAttractionProvider()


@pytest.fixture
def llm_client() -> FakeLlmClient:
    return FakeLlmClient()
