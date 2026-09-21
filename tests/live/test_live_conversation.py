"""Live smoke suite — see `tests/live/README.md` before running this.

One long conversation, mirroring the manual curl session run against the
real stack on 2026-09-20, rather than many short ones: each turn is a real
Groq call and often a real Overpass call too, so fewer, richer turns keep
this suite's cost and rate-limit pressure down for something meant to be
run occasionally by hand, not on every commit.
"""

from datetime import date, timedelta

import httpx
import pytest
from httpx import AsyncClient

from app.infrastructure.config.settings import get_settings
from app.infrastructure.providers.openweather import OpenWeatherAdapter

pytestmark = pytest.mark.live

_CHAT = "/api/v1/conversations/chat"
_KNOWN_CATEGORIES = {
    "beach",
    "museum",
    "landmark",
    "viewpoint",
    "restaurant",
    "cultural_site",
    "outdoor_activity",
    "indoor_activity",
    "nature",
    "shopping",
    "nightlife",
    "wellness",
    "wildlife",
    "adventure",
    "family",
    "photography",
    "food",
    "hiking",
    "water_sports",
    "hotel",
    "guest_house",
    "sports_facility",
}


class TestFullConversationFlow:
    """Each step asserts on structure/behavior, not exact LLM wording or
    exact Overpass result counts — those vary between runs by design (audit
    §21). A failure here should mean something is actually broken: a crash,
    a wrong intent, a context field that should have survived but didn't, or
    a place whose category isn't even a real `AttractionType`."""

    async def test_full_conversation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        # 1. Trip planning establishes the trip in one turn.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={
                "message": (
                    "I'm planning a 4-day trip to Goa from September 22 to "
                    "September 25. I love beaches and photography."
                ),
                "conversationId": None,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["contextComplete"] is True
        assert data["tripContext"]["destination"]["name"] == "Goa"
        assert data["tripContext"]["startDate"] == "2026-09-22"
        assert data["response"]  # non-empty, grounded reply
        conversation_id = data["conversationId"]

        # 2. Stays: a category this session added — never invented, so any
        # returned place must be a real `AttractionType`.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={
                "message": "Can you find me a nice hotel to stay at?",
                "conversationId": conversation_id,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "hotel" in data["tripContext"]["interests"]
        for place in data["places"]:
            assert place["type"] in _KNOWN_CATEGORIES

        # 3. Sports: same check — present or genuinely absent, never a
        # fabricated category.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={
                "message": "Any tennis courts or sports facilities nearby?",
                "conversationId": conversation_id,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["intent"] == "recommendation_request"
        for place in data["places"]:
            assert place["type"] in _KNOWN_CATEGORIES

        # 4. ISSUE-5 regression: this exact phrasing was misclassified as
        # `itinerary_request` in the original audit.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={"message": "Which day is best?", "conversationId": conversation_id},
        )
        assert response.status_code == 200
        assert response.json()["data"]["intent"] == "weather_question"

        # 5. ISSUE-1 regression: an ambiguous destination change must clear
        # `destination` (intentional, backend-side) while dates/interests
        # survive — never a silent full reset of the trip.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={
                "message": "Actually, let us go to Paris instead.",
                "conversationId": conversation_id,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contextComplete"] is False
        assert "destination" not in data["tripContext"]
        assert data["tripContext"]["startDate"] == "2026-09-22"
        assert len(data["destinationCandidates"]) > 1

        # 6. Recovery: disambiguating must fully restore `contextComplete`.
        response = await client.post(
            _CHAT,
            headers=auth_headers,
            json={"message": "1", "conversationId": conversation_id},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["contextComplete"] is True
        assert data["tripContext"]["destination"]["country"] == "France"

        # 7. Persistence: a fresh read must show every turn survived.
        response = await client.get(
            f"/api/v1/conversations/{conversation_id}", headers=auth_headers
        )
        assert response.status_code == 200
        assert len(response.json()["data"]["messages"]) == 12


class TestProviderHealth:
    """No LLM call needed — cheap enough to run on its own, but order-
    sensitive within a process: `ProviderRegistry` is an `lru_cache`
    singleton, so this only holds if nothing earlier in the same run forced
    a fallback provider to actually be called (a legitimate, different
    state, not a regression)."""

    async def test_unprobed_providers_report_unknown_not_available(
        self, client: AsyncClient, ops_headers: dict[str, str]
    ) -> None:
        """ISSUE-3 regression: a provider that has never been called must
        not be reported as `available` — that reads as "verified reachable"
        to an operator when it means nothing of the sort."""
        response = await client.get("/api/v1/providers/health", headers=ops_headers)
        assert response.status_code == 200
        providers = {p["provider"]: p["status"] for p in response.json()["data"]["providers"]}
        assert "meteostat" in providers  # historical-only; can never have been called here
        assert providers["meteostat"] == "unknown"


class TestOpenWeatherFallback:
    """ISSUE-7 (E2E audit): the fallback providers were wired and unit-
    tested against fakes, but never exercised against the real API — no
    key was configured. Calls the adapter directly rather than through the
    registry: `open_meteo` (the primary) is healthy, so a chat turn would
    never actually reach this provider to prove the credential works."""

    async def test_fetches_real_forecast_data(self) -> None:
        settings = get_settings()
        if not settings.openweather_api_key:
            pytest.skip("OPENWEATHER_API_KEY not configured")

        client = httpx.AsyncClient(timeout=10.0)
        adapter = OpenWeatherAdapter(
            client,
            api_key=settings.openweather_api_key,
            retry_attempts=settings.provider_retry_attempts,
            retry_backoff_seconds=settings.provider_retry_backoff_seconds,
        )
        try:
            start = date.today() + timedelta(days=1)
            end = start + timedelta(days=2)
            readings = await adapter.fetch(15.2993, 74.1240, start, end)
        finally:
            await client.aclose()

        assert len(readings) > 0
        for reading in readings:
            assert -90 <= reading.temp_min_c <= 60
            assert reading.temp_min_c <= reading.temp_max_c
            assert 0.0 <= reading.precipitation_probability <= 1.0
