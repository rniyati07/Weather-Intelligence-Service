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


class TestConcreteResponseSchemas:
    """The published contract must name each endpoint's real payload type.

    An untyped `data` erases the payload from OpenAPI and makes client
    codegen produce unusable types.
    """

    _EXPECTED_PAYLOADS = {
        ("get", "/api/v1/locations/{location_id}/intelligence"): "WeatherIntelligenceSchema",
        (
            "get",
            "/api/v1/locations/{location_id}/intelligence/best-days",
        ): "BestDaysViewSchema",
        ("get", "/api/v1/locations/{location_id}/intelligence/packing"): "PackingViewSchema",
        ("get", "/api/v1/locations/{location_id}/weather/raw"): "RawWeatherViewSchema",
        (
            "post",
            "/api/v1/locations/{location_id}/intelligence/narrative",
        ): "NarrativeViewSchema",
        ("get", "/api/v1/providers/health"): "ProviderHealthViewSchema",
    }

    def test_every_endpoint_references_its_concrete_payload(self, app: Any) -> None:
        schema = app.openapi()
        for (method, path), payload in self._EXPECTED_PAYLOADS.items():
            ref = schema["paths"][path][method]["responses"]["200"]["content"][
                "application/json"
            ]["schema"]["$ref"]
            assert payload in ref, f"{method.upper()} {path} does not publish {payload}"

    def test_payload_schemas_are_defined_in_components(self, app: Any) -> None:
        defined = app.openapi()["components"]["schemas"]
        for payload in set(self._EXPECTED_PAYLOADS.values()):
            assert payload in defined

    def test_data_field_is_not_untyped(self, app: Any) -> None:
        schemas = app.openapi()["components"]["schemas"]
        envelopes = [name for name in schemas if name.startswith("ResponseEnvelope")]
        assert envelopes, "no parameterised envelope was generated"
        for name in envelopes:
            data = schemas[name]["properties"]["data"]
            # `anyOf: [{}, null]` is the untyped shape this guards against.
            assert {} not in data.get("anyOf", []), f"{name}.data is untyped"

    def test_schema_has_no_dangling_references(self, app: Any) -> None:
        import json
        import re

        schema = app.openapi()
        defined = set(schema["components"]["schemas"])
        referenced = set(
            re.findall(r"#/components/schemas/([A-Za-z0-9_]+)", json.dumps(schema))
        )
        assert not (referenced - defined)


class TestPublishedAuthentication:
    """Authentication must be discoverable from the contract, not just enforced."""

    def test_api_key_security_scheme_is_published(self, app: Any) -> None:
        schemes = app.openapi()["components"]["securitySchemes"]
        assert "APIKeyHeader" in schemes
        assert schemes["APIKeyHeader"]["type"] == "apiKey"
        assert schemes["APIKeyHeader"]["in"] == "header"
        assert schemes["APIKeyHeader"]["name"] == "X-API-Key"

    def test_every_protected_endpoint_declares_security(self, app: Any) -> None:
        schema = app.openapi()
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                if path == "/health":
                    continue  # unauthenticated liveness probe, by design
                assert operation.get("security"), f"{method.upper()} {path} declares no security"

    def test_api_key_is_not_documented_as_an_optional_header(self, app: Any) -> None:
        schema = app.openapi()
        for path, methods in schema["paths"].items():
            for operation in methods.values():
                optional_key_params = [
                    p
                    for p in operation.get("parameters", [])
                    if p["name"].lower() == "x-api-key" and not p.get("required")
                ]
                assert not optional_key_params, f"{path} documents X-API-Key as optional"


class TestNoPhantomStatusCodes:
    """The contract must not advertise a status the service cannot return."""

    def test_no_operation_declares_422(self, app: Any) -> None:
        schema = app.openapi()
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                assert "422" not in operation["responses"], (
                    f"{method.upper()} {path} declares 422, but validation returns 400"
                )

    def test_validation_only_schemas_are_not_published(self, app: Any) -> None:
        defined = app.openapi()["components"]["schemas"]
        assert "HTTPValidationError" not in defined
        assert "ValidationError" not in defined


class TestDocsEndpoints:
    async def test_swagger_ui_serves(self, client: AsyncClient) -> None:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    async def test_openapi_json_serves(self, client: AsyncClient) -> None:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert response.json()["info"]["title"] == "Weather Intelligence Service"
