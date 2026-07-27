"""Tests for `LlmClient`: retry only on transient failures, hard failure on 4xx,
and a working happy path. Offline via respx, mirroring the Phase 4 provider tests."""

import json

import httpx
import pytest
import respx

from app.infrastructure.ai.llm_client import LlmClient, LlmClientError, LlmTimeoutError

_BASE_URL = "https://api.example-llm.test/v1"
_URL = f"{_BASE_URL}/chat/completions"


def _client(base_url: str = _BASE_URL) -> LlmClient:
    return LlmClient(
        httpx.AsyncClient(),
        base_url=base_url,
        api_key="test-key",
        model="test-model",
        timeout_seconds=5.0,
        max_output_tokens=400,
    )


class TestSuccess:
    @respx.mock
    async def test_returns_message_content(self) -> None:
        respx.post(_URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "A calm, sunny trip ahead."}}]}
            )
        )
        result = await _client().complete(system_prompt="sys", user_content="go")
        assert result == "A calm, sunny trip ahead."

    @respx.mock
    async def test_sends_model_and_max_tokens(self) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        )
        await _client().complete(system_prompt="sys", user_content="go")
        sent_body = json.loads(route.calls.last.request.content)
        assert sent_body["model"] == "test-model"
        assert sent_body["max_tokens"] == 400


class TestRetryBehavior:
    @respx.mock
    async def test_4xx_does_not_retry(self) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
        with pytest.raises(LlmClientError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 1

    @respx.mock
    async def test_5xx_retries_once_then_raises(self) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(500))
        with pytest.raises(LlmClientError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 2  # 1 initial + 1 retry

    @respx.mock
    async def test_timeout_raises_llm_timeout_error(self) -> None:
        route = respx.post(_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        with pytest.raises(LlmTimeoutError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 2  # 1 initial + 1 retry

    @respx.mock
    async def test_malformed_response_fails_without_retry(self) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(200, json={"unexpected": True}))
        with pytest.raises(LlmClientError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 1
