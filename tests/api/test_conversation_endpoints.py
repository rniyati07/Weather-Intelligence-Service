"""Contract tests for `/conversations` and `/conversations/chat`.

Mirrors `tests/api/conftest.py`'s override pattern: only outbound
dependencies are replaced, so this suite exercises real routing, auth,
validation, envelope shape, and error mapping — offline, no network, no
database.
"""

from collections.abc import AsyncIterator
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.domain.ports.attractions import AttractionPort
from app.domain.ports.geocoding import GeocodingPort
from app.interface.http import dependencies as deps
from app.main import create_app
from tests.api.conftest import API_KEY, FakeNarration, FakeRegistry, FakeRepository
from tests.application.conftest import (
    GOA,
    PARIS_FRANCE,
    PARIS_TEXAS,
    FakeAttractionProvider,
    FakeConversationRepository,
    FakeGeocoding,
    FakeIntelligenceUseCase,
    FakeLlmClient,
    make_attraction_recommendation,
)

_START = date.today() + timedelta(days=5)
_END = _START + timedelta(days=3)


@pytest.fixture
def conversation_repo() -> FakeConversationRepository:
    return FakeConversationRepository()


@pytest.fixture
def geocoding() -> GeocodingPort:
    return FakeGeocoding(results={"goa": [GOA]})


@pytest.fixture
def intelligence_use_case() -> FakeIntelligenceUseCase:
    return FakeIntelligenceUseCase()


@pytest.fixture
def attraction_provider() -> AttractionPort:
    return FakeAttractionProvider()


@pytest.fixture
def llm_client() -> FakeLlmClient:
    return FakeLlmClient(
        extraction_response=(
            f'{{"destination": "Goa", "startDate": "{_START.isoformat()}", '
            f'"endDate": "{_END.isoformat()}"}}'
        )
    )


@pytest.fixture
def app(
    conversation_repo: FakeConversationRepository,
    geocoding: GeocodingPort,
    intelligence_use_case: FakeIntelligenceUseCase,
    attraction_provider: AttractionPort,
    llm_client: FakeLlmClient,
) -> Any:
    """The real application with chat's outbound dependencies overridden.

    Weather-endpoint dependencies (`repository`/`registry`/`narration`) are
    still overridden too — `create_app()` wires every router, and those
    other endpoints must keep working offline in this suite the same as in
    `tests/api/conftest.py`.
    """
    application = create_app()

    async def _session_override() -> AsyncIterator[None]:
        yield None

    application.dependency_overrides[deps.get_db_session] = _session_override
    application.dependency_overrides[deps.get_weather_repository] = lambda: FakeRepository()
    application.dependency_overrides[deps.get_provider_registry_dependency] = lambda: FakeRegistry()
    application.dependency_overrides[deps.get_narration_service_dependency] = (
        lambda: FakeNarration()
    )

    application.dependency_overrides[deps.get_conversation_repository] = lambda: conversation_repo
    application.dependency_overrides[deps.get_geocoding_dependency] = lambda: geocoding
    application.dependency_overrides[deps.get_weather_intelligence_use_case] = (
        lambda: intelligence_use_case
    )
    application.dependency_overrides[deps.get_attraction_provider] = lambda: attraction_provider
    application.dependency_overrides[deps.get_chat_llm_client_dependency] = lambda: llm_client

    settings = deps.get_settings()
    application.dependency_overrides[deps.get_app_settings] = lambda: settings.model_copy(
        update={"api_keys": [API_KEY]}
    )

    deps.reset_rate_limiter()
    deps.reset_chat_intelligence_cache()
    return application


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as async_client:
        yield async_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


class TestAuth:
    async def test_chat_without_key_is_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/conversations/chat", json={"message": "hi"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTHENTICATION_ERROR"

    async def test_create_conversation_without_key_is_401(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/conversations", json={})
        assert response.status_code == 401


class TestCreateConversation:
    async def test_create_returns_envelope_with_empty_context(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post("/api/v1/conversations", json={}, headers=auth_headers)

        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True
        assert body["data"]["conversation"]["tripContext"] == {}
        assert body["data"]["conversation"]["messages"] == []

    async def test_create_with_initial_message_appends_it(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations",
            json={"initial_message": "I'm planning a trip"},
            headers=auth_headers,
        )

        body = response.json()
        assert len(body["data"]["conversation"]["messages"]) == 1
        assert body["data"]["conversation"]["messages"][0]["role"] == "user"


class TestGetConversation:
    async def test_unknown_id_is_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(f"/api/v1/conversations/{uuid4()}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    async def test_malformed_id_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/conversations/not-a-uuid", headers=auth_headers)
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_created_conversation_is_retrievable(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        create_response = await client.post("/api/v1/conversations", json={}, headers=auth_headers)
        conversation_id = create_response.json()["data"]["conversation"]["id"]

        response = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["data"]["id"] == conversation_id


class TestListConversations:
    async def test_lists_active_conversations_from_the_repository(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """Regression: this endpoint used to hardcode `return []`."""
        await client.post("/api/v1/conversations", json={}, headers=auth_headers)
        await client.post("/api/v1/conversations", json={}, headers=auth_headers)

        response = await client.get("/api/v1/conversations", headers=auth_headers)

        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    async def test_empty_when_no_conversations_exist(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/conversations", headers=auth_headers)
        assert response.json()["data"] == []


class TestChat:
    async def test_chat_creates_a_conversation_when_none_given(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I want to go to Goa"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["conversationId"] is not None
        # The fixture's LLM client always returns full trip data on any
        # extraction call, so even a destination-only message completes the
        # context here — this test asserts a conversation id was minted, not
        # completion state (see TestChat's other cases for that).
        assert body["contextComplete"] is True

    async def test_full_trip_message_completes_context_and_returns_envelope(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I'm planning a trip to Goa from August 20 to August 23"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["contextComplete"] is True
        assert body["tripContext"]["destination"]["name"] == "Goa"
        assert body["missingEssentials"] == []

    async def test_unknown_conversation_id_is_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "hi", "conversation_id": str(uuid4())},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_empty_message_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat", json={"message": ""}, headers=auth_headers
        )
        assert response.status_code == 400

    async def test_conversation_persists_across_two_chat_calls(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = await client.post(
            "/api/v1/conversations/chat", json={"message": "Goa"}, headers=auth_headers
        )
        conversation_id = first.json()["data"]["conversationId"]

        second = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "and I like beaches", "conversation_id": conversation_id},
            headers=auth_headers,
        )

        assert second.status_code == 200
        assert second.json()["data"]["conversationId"] == conversation_id
        assert second.json()["data"]["tripContext"]["destination"]["name"] == "Goa"


class TestChatResponseContractFields:
    """Backend gap 2: `intent` and `llmGenerated` must be real, present
    fields on the wire response — not just internal `ChatResult` state."""

    async def test_completing_turn_exposes_intent_and_llm_generated(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I'm planning a trip to Goa from August 20 to August 23"},
            headers=auth_headers,
        )

        body = response.json()["data"]
        assert body["intent"] == "trip_planning"
        assert body["llmGenerated"] is True
        assert body["places"] == []  # this suite's attraction fixture returns none
        assert body["destinationCandidates"] == []


class TestClarificationTurnContractFields:
    """A separate `llm_client` override: the module fixture's LLM client
    always returns full trip data on any extraction call (see `TestChat`'s
    docstring), which never leaves a message actually incomplete — this
    class uses one that genuinely extracts nothing."""

    @pytest.fixture
    def llm_client(self) -> FakeLlmClient:
        return FakeLlmClient(extraction_response="{}")

    async def test_clarification_turn_exposes_intent_and_llm_generated_false(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat", json={"message": "hi there"}, headers=auth_headers
        )

        body = response.json()["data"]
        assert body["contextComplete"] is False
        assert body["intent"] == "trip_planning"
        assert body["llmGenerated"] is False


class TestChatResponsePlaces:
    """Backend gap 1: real places, sourced from the Places provider, exposed
    as structured fields the frontend can render without parsing prose."""

    @pytest.fixture
    def attraction_provider(self) -> FakeAttractionProvider:
        return FakeAttractionProvider(
            recommendation=make_attraction_recommendation(start=_START, end=_END)
        )

    async def test_places_are_returned_with_the_documented_shape(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I'm planning a trip to Goa from August 20 to August 23"},
            headers=auth_headers,
        )

        places = response.json()["data"]["places"]
        assert {p["name"] for p in places} == {"Baga Beach", "Museum of Christian Art"}
        beach = next(p for p in places if p["name"] == "Baga Beach")
        assert beach["type"] == "beach"
        assert beach["latitude"] == pytest.approx(15.5553)
        assert beach["weatherSuitability"] == "ideal"
        assert "reason" in beach
        # No provider-internal id (e.g. an OSM node reference) is exposed.
        assert "id" not in beach


class TestDestinationClarificationEndpoint:
    """Backend gap 3, at the real HTTP contract level."""

    @pytest.fixture
    def geocoding(self) -> GeocodingPort:
        return FakeGeocoding(results={"paris": [PARIS_FRANCE, PARIS_TEXAS]})

    @pytest.fixture
    def llm_client(self) -> FakeLlmClient:
        # The module fixture's extraction always says "Goa" regardless of
        # message text; this class needs the (fake) understanding call to
        # actually report the destination named in the test's own message.
        return FakeLlmClient(extraction_response='{"destination": "Paris"}')

    async def test_ambiguous_destination_returns_structured_candidates(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I'm planning a trip to Paris."},
            headers=auth_headers,
        )

        body = response.json()["data"]
        assert body["contextComplete"] is False
        assert body["tripContext"].get("destination") is None
        candidates = body["destinationCandidates"]
        assert len(candidates) == 2
        assert {c["country"] for c in candidates} == {"France", "United States"}
        for candidate in candidates:
            assert "latitude" in candidate and "longitude" in candidate
            assert "displayName" in candidate

    async def test_selecting_a_candidate_resolves_the_trip_on_the_next_turn(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        first = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "I'm planning a trip to Paris."},
            headers=auth_headers,
        )
        conversation_id = first.json()["data"]["conversationId"]

        second = await client.post(
            "/api/v1/conversations/chat",
            json={"message": "the one in France", "conversation_id": conversation_id},
            headers=auth_headers,
        )

        body = second.json()["data"]
        assert body["tripContext"]["destination"]["country"] == "France"
        assert body["destinationCandidates"] == []


class TestRateLimit:
    async def test_chat_is_rate_limited_like_other_endpoints(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        deps.reset_rate_limiter()
        settings = deps.get_settings()
        for _ in range(settings.rate_limit_per_minute):
            await client.post(
                "/api/v1/conversations/chat", json={"message": "hi"}, headers=auth_headers
            )

        response = await client.post(
            "/api/v1/conversations/chat", json={"message": "hi"}, headers=auth_headers
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
