"""Thin HTTP client for a single LLM chat-completion call.

No orchestration framework, no agent loop, no tool use (Bible ADR-006/011)
— one request, at most one retry on a transient failure (timeout, 5xx, or a
429 rate limit; never on any other 4xx), and a hard output-token cap. This is
the only module that knows the LLM's wire format; `narration_service.py`
never touches `httpx`.
"""

import asyncio
from functools import lru_cache
from typing import Any

import httpx

from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.providers.base import build_http_client

#: Fallback delay before the one retry on a 429, when the provider gives no
#: `Retry-After` header. Live-observed: a short burst of chat turns (a user
#: asking several follow-up questions in quick succession, each needing an
#: extraction call and a narrative call) can trip Groq's per-minute rate
#: limit; retrying instantly almost always hits the same wall again, so a
#: brief wait is what actually gives the retry a chance to succeed.
_DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 1.5
#: Upper bound on how long a single request will wait on a provider-supplied
#: `Retry-After`, so a misbehaving provider can't stall a chat turn for
#: minutes.
_MAX_RATE_LIMIT_BACKOFF_SECONDS = 5.0


class LlmClientError(Exception):
    """Raised when the LLM call fails (non-transient failure, or retry exhausted)."""


class LlmTimeoutError(LlmClientError):
    """Raised when the LLM call exceeds `LLM_TIMEOUT_SECONDS`."""


def _is_transient(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code >= 500 or exc.response.status_code == 429


def _retry_after_seconds(response: httpx.Response) -> float:
    """How long to wait before retrying a 429, from `Retry-After` if given.

    The header is normally an integer count of seconds for a rate limit
    (the HTTP-date form is for cache-style 503s, not something a rate
    limiter sends) — parsed defensively since it's provider-controlled
    input, with the default and a cap so a missing or unreasonable value
    never turns into either no wait or an excessive one.
    """
    raw = response.headers.get("retry-after")
    if raw is None:
        return _DEFAULT_RATE_LIMIT_BACKOFF_SECONDS
    try:
        seconds = float(raw)
    except ValueError:
        return _DEFAULT_RATE_LIMIT_BACKOFF_SECONDS
    return max(0.0, min(seconds, _MAX_RATE_LIMIT_BACKOFF_SECONDS))


class LlmClient:
    """A single chat-completions call against an OpenAI-compatible `LLM_BASE_URL`."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    async def complete(
        self,
        *,
        system_prompt: str,
        user_content: str,
        json_mode: bool = False,
        temperature: float | None = None,
    ) -> str:
        """Call the chat-completions endpoint once; retry once on a transient failure.

        `json_mode` sets the OpenAI-compatible `response_format:
        {"type": "json_object"}` — Gemini's OpenAI-compat layer honours it,
        and it materially improves reliability over prompt-only "return
        JSON" instructions for the structured extraction call. It does not
        replace the caller's own `json.loads` + validation: a model can
        still return syntactically valid JSON that doesn't match the
        requested shape, so the caller must keep treating the result as
        untrusted input.

        `temperature`, left unset, uses the provider's own default — right
        for narrative generation, which wants some natural variation.
        Structured extraction is a different kind of task (read the message,
        report what's there) where that same variation is pure risk: an
        obvious, explicitly-stated destination or date can still be dropped
        on an unlucky sampling draw. The caller passes a low value there.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self._max_output_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if temperature is not None:
            payload["temperature"] = temperature
        headers = {"Authorization": f"Bearer {self._api_key}"}

        attempts_allowed = 2  # at most one retry
        for attempt in range(attempts_allowed):
            is_last_attempt = attempt == attempts_allowed - 1
            try:
                response = await self._client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                content = choice["message"].get("content")
                finish_reason = choice.get("finish_reason")

                # A reasoning model spends part of `max_tokens` on hidden
                # thinking before emitting text. If the budget runs out the
                # response comes back either as `content: null` or as text
                # cut off mid-sentence, both with `finish_reason: "length"`.
                # Neither may reach a user: `str(None)` would yield the
                # literal "None", and truncated prose is worse than no
                # narration at all, since both pass a non-empty check.
                if not isinstance(content, str):
                    raise LlmClientError(
                        f"LLM returned no text content (finish_reason={finish_reason!r}); "
                        f"the model may have exhausted "
                        f"max_tokens={self._max_output_tokens} on reasoning before emitting text."
                    )
                if finish_reason == "length":
                    raise LlmClientError(
                        f"LLM output was truncated (finish_reason='length') at "
                        f"max_tokens={self._max_output_tokens}; raise LLM_MAX_OUTPUT_TOKENS."
                    )
                return content
            except httpx.TimeoutException as exc:
                if is_last_attempt:
                    raise LlmTimeoutError(f"LLM call timed out: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                if not _is_transient(exc) or is_last_attempt:
                    raise LlmClientError(f"LLM call failed: {exc}") from exc
                if exc.response.status_code == 429:
                    await asyncio.sleep(_retry_after_seconds(exc.response))
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                # Connection errors and malformed responses are never retried:
                # a malformed response won't fix itself on a second attempt.
                raise LlmClientError(f"LLM call failed: {exc}") from exc

        raise LlmClientError("LLM call failed: retry attempts exhausted")

    async def aclose(self) -> None:
        """Close the HTTP client this instance was constructed with."""
        await self._client.aclose()


def build_chat_llm_client(settings: Settings, http_client: httpx.AsyncClient) -> LlmClient:
    """Wire an `LlmClient` for direct chat use (entity extraction, chat response).

    Same settings, same class as `narration_service.build_narration_service` —
    intentionally not a second implementation, just a second call site
    against the one LLM transport this codebase has.
    """
    return LlmClient(
        http_client,
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_output_tokens=settings.llm_max_output_tokens,
    )


@lru_cache
def get_chat_llm_client() -> LlmClient:
    """Return the process-wide chat `LlmClient`, constructed on first call.

    Its own client and cache entry, separate from `NarrationService`'s: chat
    extraction/response and narration are independent call sites with
    independent failure modes, and sharing a pool would let one exhaust the
    other exactly as the weather-vs-geocoding split does.
    """
    settings = get_settings()
    http_client = build_http_client(settings.llm_timeout_seconds)
    return build_chat_llm_client(settings, http_client)
