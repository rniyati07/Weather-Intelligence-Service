"""Tests for `LlmClient`: retry only on transient failures, hard failure on 4xx,
and a working happy path. Offline via respx, mirroring the Phase 4 provider tests."""

import json

import httpx
import pytest
import respx

from app.infrastructure.ai.llm_client import (
    _DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
    _MAX_RATE_LIMIT_BACKOFF_SECONDS,
    LlmClient,
    LlmClientError,
    LlmTimeoutError,
    _retry_after_seconds,
)

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

    @respx.mock
    async def test_json_mode_sets_response_format(self) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
        )
        await _client().complete(system_prompt="sys", user_content="go", json_mode=True)
        sent_body = json.loads(route.calls.last.request.content)
        assert sent_body["response_format"] == {"type": "json_object"}

    @respx.mock
    async def test_json_mode_defaults_to_off(self) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        )
        await _client().complete(system_prompt="sys", user_content="go")
        sent_body = json.loads(route.calls.last.request.content)
        assert "response_format" not in sent_body

    @respx.mock
    async def test_temperature_is_sent_when_given(self) -> None:
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        )
        await _client().complete(system_prompt="sys", user_content="go", temperature=0.1)
        sent_body = json.loads(route.calls.last.request.content)
        assert sent_body["temperature"] == 0.1

    @respx.mock
    async def test_temperature_omitted_by_default(self) -> None:
        """Left unset, the provider's own default temperature applies —
        right for narrative generation, which wants natural variation."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
        )
        await _client().complete(system_prompt="sys", user_content="go")
        sent_body = json.loads(route.calls.last.request.content)
        assert "temperature" not in sent_body


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

    @respx.mock
    async def test_429_retries_once_then_raises(self) -> None:
        """A rate limit is transient too — live-observed: a burst of chat
        turns can trip Groq's per-minute limit, and treating 429 like any
        other 4xx meant an instant, unnecessary fallback to the generic
        template instead of giving the one retry a chance to land after the
        window resets. `Retry-After: 0` keeps this test from actually
        sleeping; the backoff duration itself is covered separately."""
        route = respx.post(_URL).mock(
            return_value=httpx.Response(429, headers={"Retry-After": "0"})
        )
        with pytest.raises(LlmClientError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 2  # 1 initial + 1 retry

    @respx.mock
    async def test_429_succeeds_on_retry(self) -> None:
        route = respx.post(_URL).mock(
            side_effect=[
                httpx.Response(429, headers={"Retry-After": "0"}),
                httpx.Response(200, json={"choices": [{"message": {"content": "ok now"}}]}),
            ]
        )
        result = await _client().complete(system_prompt="sys", user_content="go")
        assert result == "ok now"
        assert route.call_count == 2

    @respx.mock
    async def test_other_4xx_still_does_not_retry(self) -> None:
        route = respx.post(_URL).mock(return_value=httpx.Response(400, json={"error": "bad"}))
        with pytest.raises(LlmClientError):
            await _client().complete(system_prompt="sys", user_content="go")
        assert route.call_count == 1


class TestRetryAfterParsing:
    """`_retry_after_seconds` in isolation — no network, no real sleep."""

    def test_missing_header_uses_default(self) -> None:
        response = httpx.Response(429)
        assert _retry_after_seconds(response) == _DEFAULT_RATE_LIMIT_BACKOFF_SECONDS

    def test_malformed_header_uses_default(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "not-a-number"})
        assert _retry_after_seconds(response) == _DEFAULT_RATE_LIMIT_BACKOFF_SECONDS

    def test_valid_header_within_cap_is_used(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "2"})
        assert _retry_after_seconds(response) == 2.0

    def test_header_above_cap_is_clamped(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "120"})
        assert _retry_after_seconds(response) == _MAX_RATE_LIMIT_BACKOFF_SECONDS

    def test_negative_header_is_clamped_to_zero(self) -> None:
        response = httpx.Response(429, headers={"Retry-After": "-5"})
        assert _retry_after_seconds(response) == 0.0


_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
_GEMINI_URL = f"{_GEMINI_BASE_URL}/chat/completions"


def _gemini_client() -> LlmClient:
    return LlmClient(
        httpx.AsyncClient(),
        base_url=_GEMINI_BASE_URL,
        api_key="gemini-key",
        model="gemini-2.5-flash",
        timeout_seconds=8.0,
        max_output_tokens=400,
    )


class TestGeminiCompatibility:
    """Wire-level compatibility with Gemini's OpenAI-compatible endpoint.

    Gemini is reached through the same OpenAI-shaped client (no Gemini SDK):
    `{base}/chat/completions`, `Authorization: Bearer <key>`, and a
    `model`/`messages`/`max_tokens` payload.
    """

    @respx.mock
    async def test_request_shape_matches_gemini_openai_endpoint(self) -> None:
        route = respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "content": "Goa looks stormy."},
                         "finish_reason": "stop"}
                    ],
                    "model": "gemini-2.5-flash",
                },
            )
        )

        result = await _gemini_client().complete(system_prompt="sys", user_content="go")

        request = route.calls.last.request
        assert str(request.url) == _GEMINI_URL
        assert request.headers["authorization"] == "Bearer gemini-key"
        assert request.headers["content-type"] == "application/json"

        body = json.loads(request.content)
        assert body["model"] == "gemini-2.5-flash"
        assert body["max_tokens"] == 400
        assert [m["role"] for m in body["messages"]] == ["system", "user"]
        assert result == "Goa looks stormy."

    @respx.mock
    async def test_null_content_is_rejected_not_stringified(self) -> None:
        # A reasoning model that burns its whole token budget on thinking
        # returns `content: null` with `finish_reason: "length"`. Naively
        # `str()`-ing that yields the literal "None", which would sail past
        # downstream non-empty validation and reach a user as narration.
        respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"content": None}, "finish_reason": "length"}]},
            )
        )

        with pytest.raises(LlmClientError) as exc_info:
            await _gemini_client().complete(system_prompt="sys", user_content="go")

        assert "no text content" in str(exc_info.value)

    @respx.mock
    async def test_truncated_output_is_rejected(self) -> None:
        # Partial text with `finish_reason: "length"` means the model ran out
        # of budget mid-sentence. It is non-empty, so it would otherwise pass
        # downstream validation and reach a user as a cut-off narrative.
        respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {"content": "For the trip to Goa from July 29 to July"},
                            "finish_reason": "length",
                        }
                    ]
                },
            )
        )

        with pytest.raises(LlmClientError, match="truncated"):
            await _gemini_client().complete(system_prompt="sys", user_content="go")

    @respx.mock
    async def test_complete_output_with_finish_reason_stop_is_accepted(self) -> None:
        respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "A complete sentence."}, "finish_reason": "stop"}
                    ]
                },
            )
        )
        result = await _gemini_client().complete(system_prompt="sys", user_content="go")
        assert result == "A complete sentence."

    @respx.mock
    async def test_missing_content_key_is_rejected(self) -> None:
        respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant"}, "finish_reason": "length"}]},
            )
        )
        with pytest.raises(LlmClientError):
            await _gemini_client().complete(system_prompt="sys", user_content="go")

    @respx.mock
    async def test_base_url_with_trailing_slash_does_not_double_slash(self) -> None:
        route = respx.post(_GEMINI_URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
            )
        )
        client = LlmClient(
            httpx.AsyncClient(),
            base_url=_GEMINI_BASE_URL + "/",  # trailing slash, as commonly pasted
            api_key="gemini-key",
            model="gemini-2.5-flash",
            timeout_seconds=8.0,
            max_output_tokens=400,
        )

        await client.complete(system_prompt="sys", user_content="go")

        assert str(route.calls.last.request.url) == _GEMINI_URL
