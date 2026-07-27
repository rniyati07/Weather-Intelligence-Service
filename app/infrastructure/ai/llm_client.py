"""Thin HTTP client for a single LLM chat-completion call.

No orchestration framework, no agent loop, no tool use (Bible ADR-006/011)
— one request, at most one retry on a transient failure (timeout or 5xx;
never on a 4xx), and a hard output-token cap. This is the only module that
knows the LLM's wire format; `narration_service.py` never touches `httpx`.
"""

from typing import Any

import httpx


class LlmClientError(Exception):
    """Raised when the LLM call fails (non-transient failure, or retry exhausted)."""


class LlmTimeoutError(LlmClientError):
    """Raised when the LLM call exceeds `LLM_TIMEOUT_SECONDS`."""


def _is_transient(exc: httpx.HTTPStatusError) -> bool:
    return exc.response.status_code >= 500


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

    async def complete(self, *, system_prompt: str, user_content: str) -> str:
        """Call the chat-completions endpoint once; retry once on a transient failure."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": self._max_output_tokens,
        }
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
                return str(data["choices"][0]["message"]["content"])
            except httpx.TimeoutException as exc:
                if is_last_attempt:
                    raise LlmTimeoutError(f"LLM call timed out: {exc}") from exc
            except httpx.HTTPStatusError as exc:
                if not _is_transient(exc) or is_last_attempt:
                    raise LlmClientError(f"LLM call failed: {exc}") from exc
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                # Connection errors and malformed responses are never retried:
                # a malformed response won't fix itself on a second attempt.
                raise LlmClientError(f"LLM call failed: {exc}") from exc

        raise LlmClientError("LLM call failed: retry attempts exhausted")
