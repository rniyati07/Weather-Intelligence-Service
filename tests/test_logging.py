"""Unit tests for structured logging: secret redaction and request id generation."""

import re

from app.infrastructure.observability.logging import redact_secrets_processor
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
