"""Endpoint contract tests — API Spec §6 (envelope), §7 (errors), §8 (endpoints).

Runs fully offline against the real application with only its outbound
dependencies faked, so routing, auth, validation, serialisation and error
mapping are all genuinely exercised.
"""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.domain.ports.narration import NarrationFailedError
from app.domain.ports.provider_registry import AllProvidersFailedError
from app.domain.ports.weather_provider import DataClass
from tests.api.conftest import (
    END,
    LOCATION_ID,
    START,
    FakeNarration,
    FakeRegistry,
    query,
)

BASE = f"/api/v1/locations/{LOCATION_ID}"
INTELLIGENCE = f"{BASE}/intelligence"
BEST_DAYS = f"{BASE}/intelligence/best-days"
PACKING = f"{BASE}/intelligence/packing"
RAW = f"{BASE}/weather/raw"
NARRATIVE = f"{BASE}/intelligence/narrative"
HEALTH = "/api/v1/providers/health"

_ALL_GET_ENDPOINTS = [INTELLIGENCE, BEST_DAYS, PACKING, RAW]


def body() -> dict[str, str]:
    return {"startDate": START.isoformat(), "endDate": END.isoformat()}


class TestEnvelope:
    """Every response — success or failure — carries all four envelope keys."""

    @pytest.mark.parametrize("endpoint", _ALL_GET_ENDPOINTS)
    async def test_success_envelope_shape(
        self, client: AsyncClient, auth_headers: dict[str, str], endpoint: str
    ) -> None:
        response = await client.get(endpoint, params=query(), headers=auth_headers)
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"success", "data", "metadata", "error"}
        assert payload["success"] is True
        assert payload["error"] is None
        assert payload["data"] is not None

    @pytest.mark.parametrize("endpoint", _ALL_GET_ENDPOINTS)
    async def test_error_envelope_shape(self, client: AsyncClient, endpoint: str) -> None:
        response = await client.get(endpoint, params=query())  # no API key
        assert response.status_code == 401
        payload = response.json()
        assert set(payload) == {"success", "data", "metadata", "error"}
        assert payload["success"] is False
        assert payload["data"] is None
        assert payload["error"]["code"] == "AUTHENTICATION_ERROR"

    async def test_metadata_fields(
        self, client: AsyncClient, auth_headers: dict[str, str], rule_config_version: str
    ) -> None:
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        metadata = response.json()["metadata"]
        assert metadata["apiVersion"] == "1.0"
        assert metadata["requestId"].startswith("req_")
        assert metadata["cacheStatus"] in {"hit", "miss", "stale"}
        assert metadata["ruleConfigVersion"] == rule_config_version
        assert metadata["degraded"] is False
        assert "generatedAt" in metadata

    async def test_metadata_never_names_a_provider(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert "provider" not in str(response.json()["metadata"]).lower()


class TestGetIntelligence:
    async def test_returns_camelcase_intelligence(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        data = response.json()["data"]

        assert set(data) == {
            "location",
            "period",
            "dailyIntelligence",
            "tripSummary",
            "narrative",
        }
        assert data["location"]["id"] == LOCATION_ID
        assert data["period"]["startDate"] == START.isoformat()
        assert len(data["dailyIntelligence"]) == (END - START).days + 1

        day = data["dailyIntelligence"][0]
        assert set(day) == {
            "date",
            "summary",
            "riskAssessment",
            "activitySuitability",
            "packingRecommendations",
            "travelAdvisory",
        }
        assert set(day["summary"]) == {
            "tempMinC",
            "tempMaxC",
            "precipitationProbability",
            "windSpeedKph",
            "condition",
        }
        trip = data["tripSummary"]
        assert set(trip) == {
            "bestDays",
            "worstDays",
            "overallPackingList",
            "overallRiskLevel",
            "tripSuitabilityScore",
            "travelConfidence",
        }

    async def test_narrative_is_null_on_this_endpoint(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert response.json()["data"]["narrative"] is None

    async def test_storm_day_carries_explainable_rule_ids(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        first_day = response.json()["data"]["dailyIntelligence"][0]
        factors = first_day["riskAssessment"]["riskFactors"]
        assert factors, "storm fixture must produce risk factors"
        for factor in factors:
            assert set(factor) == {"type", "severity", "description", "rule"}
            assert factor["rule"]

    async def test_computed_intelligence_is_persisted(
        self, client: AsyncClient, auth_headers: dict[str, str], repository
    ) -> None:
        await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert len(repository.saved_intelligence) == (END - START).days + 1
        assert len(repository.saved_readings) == (END - START).days + 1


class TestProjections:
    async def test_best_days_view(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(BEST_DAYS, params=query(), headers=auth_headers)
        data = response.json()["data"]
        assert set(data) == {
            "location",
            "period",
            "bestDays",
            "worstDays",
            "overallRiskLevel",
        }
        assert data["bestDays"] and data["worstDays"]

    async def test_packing_view(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        response = await client.get(PACKING, params=query(), headers=auth_headers)
        data = response.json()["data"]
        assert set(data) == {"location", "period", "overallPackingList"}
        assert "waterproof jacket" in data["overallPackingList"]

    async def test_projections_agree_with_the_full_computation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        full = (await client.get(INTELLIGENCE, params=query(), headers=auth_headers)).json()["data"]
        best = (await client.get(BEST_DAYS, params=query(), headers=auth_headers)).json()["data"]
        packing = (await client.get(PACKING, params=query(), headers=auth_headers)).json()["data"]

        assert best["bestDays"] == full["tripSummary"]["bestDays"]
        assert best["worstDays"] == full["tripSummary"]["worstDays"]
        assert best["overallRiskLevel"] == full["tripSummary"]["overallRiskLevel"]
        assert packing["overallPackingList"] == full["tripSummary"]["overallPackingList"]


class TestRawWeather:
    async def test_returns_normalized_readings(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(RAW, params=query(), headers=auth_headers)
        data = response.json()["data"]
        assert set(data) == {"location", "period", "readings"}
        reading = data["readings"][0]
        assert set(reading) == {
            "date",
            "tempMinC",
            "tempMaxC",
            "precipitationProbability",
            "precipitationMm",
            "windSpeedKph",
            "humidity",
            "condition",
        }

    async def test_internal_normalization_fields_are_not_published(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(RAW, params=query(), headers=auth_headers)
        reading = response.json()["data"]["readings"][0]
        # `completeness` and `sourceClass` feed travelConfidence internally;
        # API Spec §9.9 does not publish them.
        assert "completeness" not in reading
        assert "sourceClass" not in reading


class TestNarrative:
    async def test_returns_narrative(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(NARRATIVE, json=body(), headers=auth_headers)
        assert response.status_code == 200
        data = response.json()["data"]
        assert set(data) == {"location", "period", "narrative"}
        assert set(data["narrative"]) == {
            "generatedByLlm",
            "summaryText",
            "modelUsed",
            "fallbackUsed",
        }
        assert data["narrative"]["summaryText"]

    async def test_unsupported_language_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            NARRATIVE, json={**body(), "language": "fr"}, headers=auth_headers
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_missing_body_field_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            NARRATIVE, json={"startDate": START.isoformat()}, headers=auth_headers
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_narration_failure_returns_503(
        self, app, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        from app.interface.http import dependencies as deps

        app.dependency_overrides[deps.get_narration_service_dependency] = lambda: FakeNarration(
            error=NarrationFailedError("LLM unavailable")
        )
        response = await client.post(NARRATIVE, json=body(), headers=auth_headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_DEGRADED"


class TestAuthentication:
    @pytest.mark.parametrize("endpoint", _ALL_GET_ENDPOINTS)
    async def test_missing_key_is_401(self, client: AsyncClient, endpoint: str) -> None:
        response = await client.get(endpoint, params=query())
        assert response.status_code == 401

    @pytest.mark.parametrize("endpoint", _ALL_GET_ENDPOINTS)
    async def test_wrong_key_is_401(self, client: AsyncClient, endpoint: str) -> None:
        response = await client.get(endpoint, params=query(), headers={"X-API-Key": "nope"})
        assert response.status_code == 401

    async def test_narrative_requires_a_key(self, client: AsyncClient) -> None:
        assert (await client.post(NARRATIVE, json=body())).status_code == 401


class TestOperatorEndpoint:
    async def test_ops_key_succeeds(
        self, client: AsyncClient, ops_headers: dict[str, str]
    ) -> None:
        response = await client.get(HEALTH, headers=ops_headers)
        assert response.status_code == 200
        providers = response.json()["data"]["providers"]
        assert {p["provider"] for p in providers} == {"open_meteo", "openweather"}
        assert set(providers[0]) == {"provider", "status", "lastCheckedAt"}

    async def test_consumer_key_is_forbidden(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(HEALTH, headers=auth_headers)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "AUTHORIZATION_ERROR"

    async def test_missing_key_is_401(self, client: AsyncClient) -> None:
        assert (await client.get(HEALTH)).status_code == 401


class TestValidation:
    @pytest.mark.parametrize(
        "location_id,reason",
        [
            ("not-a-coordinate", "unparseable"),
            ("15.2993", "missing longitude"),
            ("91.0,74.0", "latitude out of range"),
            ("15.0,181.0", "longitude out of range"),
            ("abc,def", "non-numeric"),
        ],
    )
    async def test_invalid_location_id_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str], location_id: str, reason: str
    ) -> None:
        response = await client.get(
            f"/api/v1/locations/{location_id}/intelligence", params=query(), headers=auth_headers
        )
        assert response.status_code == 400, reason
        payload = response.json()
        assert payload["error"]["code"] == "VALIDATION_ERROR"
        assert payload["error"]["details"]

    async def test_end_before_start_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            INTELLIGENCE,
            params={"startDate": END.isoformat(), "endDate": START.isoformat()},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["error"]["details"][0]["field"] == "endDate"

    async def test_range_beyond_horizon_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            INTELLIGENCE,
            params={
                "startDate": START.isoformat(),
                "endDate": (START + timedelta(days=40)).isoformat(),
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_malformed_date_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            INTELLIGENCE,
            params={"startDate": "not-a-date", "endDate": END.isoformat()},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    async def test_missing_required_query_param_is_400(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            INTELLIGENCE, params={"startDate": START.isoformat()}, headers=auth_headers
        )
        assert response.status_code == 400

    async def test_validation_runs_before_any_provider_call(
        self, client: AsyncClient, auth_headers: dict[str, str], registry: FakeRegistry
    ) -> None:
        calls: list[str] = []
        original = registry.fetch_with_fallback

        async def spy(*args: object, **kwargs: object):
            calls.append("fetched")
            return await original(*args, **kwargs)  # type: ignore[arg-type]

        registry.fetch_with_fallback = spy  # type: ignore[method-assign]
        await client.get(
            "/api/v1/locations/999,999/intelligence", params=query(), headers=auth_headers
        )
        assert calls == [], "provider must not be called for an invalid request"


class TestProviderFailure:
    async def test_all_providers_failed_is_503(
        self, app, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        from app.interface.http import dependencies as deps

        app.dependency_overrides[deps.get_provider_registry_dependency] = lambda: FakeRegistry(
            error=AllProvidersFailedError(DataClass.FORECAST)
        )
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"

    async def test_provider_failure_message_names_no_provider(
        self, app, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        from app.interface.http import dependencies as deps

        app.dependency_overrides[deps.get_provider_registry_dependency] = lambda: FakeRegistry(
            error=AllProvidersFailedError(DataClass.FORECAST)
        )
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        message = response.json()["error"]["message"].lower()
        for provider_name in ("open_meteo", "openweather", "weatherapi", "meteostat"):
            assert provider_name not in message

    async def test_fallback_use_is_reported_as_degraded(
        self, app, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        from app.interface.http import dependencies as deps

        app.dependency_overrides[deps.get_provider_registry_dependency] = lambda: FakeRegistry(
            used_fallback=True
        )
        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["metadata"]["degraded"] is True


class TestRateLimiting:
    async def test_exceeding_the_limit_returns_429_with_retry_after(
        self, app, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        from app.interface.http import dependencies as deps

        settings = deps.get_settings().model_copy(
            update={"api_keys": [auth_headers["X-API-Key"]], "rate_limit_per_minute": 2}
        )
        app.dependency_overrides[deps.get_app_settings] = lambda: settings

        for _ in range(2):
            assert (
                await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
            ).status_code == 200

        response = await client.get(INTELLIGENCE, params=query(), headers=auth_headers)
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "RATE_LIMITED"
        assert int(response.headers["Retry-After"]) >= 1


class TestUnknownRoute:
    async def test_unknown_route_is_404_in_the_envelope(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/nope")
        assert response.status_code == 404
        payload = response.json()
        assert payload["success"] is False
        assert payload["error"]["code"] == "NOT_FOUND"


class TestProviderIndependence:
    """No weather-data response may contain any provider name (guide §5.3)."""

    @pytest.mark.parametrize("endpoint", _ALL_GET_ENDPOINTS)
    async def test_no_provider_name_in_any_weather_response(
        self, client: AsyncClient, auth_headers: dict[str, str], endpoint: str
    ) -> None:
        response = await client.get(endpoint, params=query(), headers=auth_headers)
        raw_body = response.text.lower()
        for provider_name in ("open_meteo", "open-meteo", "openweather", "weatherapi", "meteostat"):
            assert provider_name not in raw_body

    async def test_narrative_response_names_no_provider(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(NARRATIVE, json=body(), headers=auth_headers)
        raw_body = response.text.lower()
        for provider_name in ("open_meteo", "open-meteo", "openweather", "weatherapi", "meteostat"):
            assert provider_name not in raw_body
