"""Unit tests for structured logging: secret redaction and request id generation."""

import logging
import re

from app.infrastructure.observability.logging import RedactingFilter, redact_secrets_processor
from app.infrastructure.observability.redaction import redact_text
from app.infrastructure.observability.request_context import generate_request_id


class TestRedaction:
    def test_known_secret_fields_are_redacted(self):
        event = {
            "event": "llm_call",
            "llm_api_key": "sk-super-secret",
            "openweather_api_key": "ow-secret",
            "weatherapi_key": "wa-secret",
            "meteostat_api_key": "ms-secret",
            "api_keys": ["dev_key_local"],
            "ops_api_keys": ["dev_ops_key_local"],
        }

        result = redact_secrets_processor(None, "info", event)

        for field in (
            "llm_api_key",
            "openweather_api_key",
            "weatherapi_key",
            "meteostat_api_key",
            "api_keys",
            "ops_api_keys",
        ):
            assert result[field] == "***REDACTED***"

    def test_secret_shaped_keys_are_redacted_defensively(self):
        event = {"authorization": "Bearer abc123", "user_token": "xyz", "db_password": "hunter2"}
        result = redact_secrets_processor(None, "info", event)
        assert all(value == "***REDACTED***" for value in result.values())

    def test_non_secret_fields_are_untouched(self):
        event = {"event": "request_handled", "status_code": 200, "path": "/health"}
        result = redact_secrets_processor(None, "info", event)
        assert result == event


class TestRequestId:
    def test_generate_request_id_matches_documented_shape(self):
        request_id = generate_request_id()
        assert re.fullmatch(r"req_[0-9a-f]{8}", request_id)

    def test_generate_request_id_is_unique(self):
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100


class TestCredentialRedaction:
    """Credentials embedded in URLs and headers — the paths key-name redaction misses."""

    def test_provider_query_credentials_are_redacted(self):
        line = (
            "HTTP Request: GET https://api.openweathermap.org/data/2.5/forecast"
            "?lat=48.8&lon=2.3&appid=6603946cd3ea4137b0f2897750d357b4&units=metric"
        )
        result = redact_text(line)

        assert "6603946cd3ea4137b0f2897750d357b4" not in result
        assert "appid=***REDACTED***" in result
        # Everything useful survives.
        assert "api.openweathermap.org/data/2.5/forecast" in result
        assert "lat=48.8" in result

    def test_every_credential_param_name_is_covered(self):
        for param in ("appid", "apikey", "api_key", "key", "token", "access_token", "x-api-key"):
            result = redact_text(f"https://example.com/v1?{param}=SUPERSECRET&lat=1")
            assert "SUPERSECRET" not in result, param

    def test_authorization_scheme_is_kept_but_token_is_not(self):
        # The scheme must not be mistaken for the value — that would leave the
        # token exposed while looking redacted.
        assert (
            redact_text("Authorization: Bearer sk-secret") == "Authorization: Bearer ***REDACTED***"
        )
        assert redact_text("Bearer sk-secret") == "Bearer ***REDACTED***"
        assert redact_text("X-API-Key: dev_key") == "X-API-Key: ***REDACTED***"

    def test_credential_free_urls_are_untouched(self):
        line = "GET https://api.open-meteo.com/v1/forecast?latitude=48.8&daily=temperature_2m_max"
        assert redact_text(line) == line

    def test_credential_inside_a_non_secret_field_is_redacted(self):
        # `provider_fetch_failed` logs the error string under `error`; no
        # key-name rule would ever catch a URL hiding in there.
        event = {
            "event": "provider_fetch_failed",
            "provider": "openweather",
            "error": "HTTP 401 for https://api.openweathermap.org/data/2.5/forecast?appid=LEAKED",
        }
        result = redact_secrets_processor(None, "warning", event)

        assert "LEAKED" not in result["error"]
        assert result["provider"] == "openweather"
        assert result["event"] == "provider_fetch_failed"

    def test_stdlib_filter_scrubs_httpx_request_lines(self):
        record = logging.LogRecord(
            name="httpx",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=(
                "HTTP Request: GET "
                'https://api.weatherapi.com/v1/forecast.json?key=WAKEY "HTTP/1.1 200 OK"'
            ),
            args=(),
            exc_info=None,
        )

        assert RedactingFilter().filter(record) is True
        assert "WAKEY" not in record.getMessage()
        assert "HTTP/1.1 200 OK" in record.getMessage()
