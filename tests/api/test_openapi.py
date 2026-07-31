"""OpenAPI/Swagger quality checks — no undocumented endpoints, docs render.

Guards the generated contract itself: every documented path from API Spec
§8 is present, every operation is described, and `/docs` serves.
"""

from typing import Any

from httpx import AsyncClient

#: The six documented endpoints (API Spec §8) plus the liveness probe.
_EXPECTED_PATHS = {
    ("get", "/api/v1/locations/{location_id}/intelligence"),
    ("get", "/api/v1/locations/{location_id}/intelligence/best-days"),
    ("get", "/api/v1/locations/{location_id}/intelligence/packing"),
    ("get", "/api/v1/locations/{location_id}/weather/raw"),
    ("post", "/api/v1/locations/{location_id}/intelligence/narrative"),
    ("get", "/api/v1/providers/health"),
    ("get", "/health"),
}


def _operations(schema: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (method, path)
        for path, methods in schema["paths"].items()
        for method in methods
    }


class TestOpenApiSchema:
    def test_every_documented_endpoint_is_present(self, app: Any) -> None:
        assert _operations(app.openapi()) == _EXPECTED_PATHS

    def test_no_undocumented_endpoints(self, app: Any) -> None:
        extra = _operations(app.openapi()) - _EXPECTED_PATHS
        assert not extra, f"undocumented endpoints exposed: {extra}"

    def test_every_operation_has_a_summary_and_description(self, app: Any) -> None:
        schema = app.openapi()
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                assert operation.get("summary"), f"{method.upper()} {path} has no summary"
                assert operation.get("description"), f"{method.upper()} {path} has no description"

    def test_documented_error_statuses_are_declared(self, app: Any) -> None:
        schema = app.openapi()
        intelligence = schema["paths"]["/api/v1/locations/{location_id}/intelligence"]["get"]
        for expected_status in ("400", "401", "429", "503"):
            assert expected_status in intelligence["responses"]

    def test_operator_endpoint_declares_403(self, app: Any) -> None:
        health = app.openapi()["paths"]["/api/v1/providers/health"]["get"]
        assert "403" in health["responses"]

    def test_narrative_declares_a_request_body(self, app: Any) -> None:
        narrative = app.openapi()["paths"][
            "/api/v1/locations/{location_id}/intelligence/narrative"
        ]["post"]
        assert "requestBody" in narrative

    def test_schema_version_and_title(self, app: Any) -> None:
        schema = app.openapi()
        assert schema["openapi"].startswith("3.")
        assert schema["info"]["title"] == "Weather Intelligence Service"
        assert schema["info"]["version"] == "1.0"


class TestDocsEndpoints:
    async def test_swagger_ui_serves(self, client: AsyncClient) -> None:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    async def test_openapi_json_serves(self, client: AsyncClient) -> None:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"] == "Weather Intelligence Service"
