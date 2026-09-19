"""Shared HTTP plumbing for provider adapters.

One timeout policy, one retry policy, two typed errors — every adapter uses
these instead of rolling its own `httpx` and `tenacity` setup. Retries apply
only to transient failures (connection errors, timeouts, 5xx); a 4xx never
retries and fails immediately.
"""

from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_exponential

T = TypeVar("T")


class ProviderError(Exception):
    """Raised when a provider call fails: a non-retryable 4xx, or retries exhausted."""

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderTimeoutError(ProviderError):
    """Raised when a provider call exceeds its configured timeout."""


def _is_transient(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException | httpx.ConnectError):
        return True
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500


#: Sent on every outbound provider call.
#:
#: Not cosmetic: Overpass rejects httpx's default `python-httpx/x.y.z` agent
#: outright with `406 Not Acceptable`, so every places lookup failed and every
#: chat turn silently came back with no attractions. Identifying the client is
#: also what Overpass's own usage policy asks of API consumers, and the other
#: providers accept it without complaint — so it belongs on the shared client
#: rather than in one adapter.
USER_AGENT = "WeatherIntelligenceService/1.0 (+https://github.com/weather-intelligence-service)"


def build_http_client(timeout_seconds: float) -> httpx.AsyncClient:
    """Build the pooled client an adapter is constructed with (one per process, shared)."""
    return httpx.AsyncClient(timeout=timeout_seconds, headers={"User-Agent": USER_AGENT})


async def call_with_retry(
    request: Callable[[], Awaitable[T]],
    *,
    provider: str,
    attempts: int,
    backoff_seconds: float,
) -> T:
    """Run `request`, retrying only transient errors, and translate failures.

    `attempts` is the number of *retries* after the first try (so total
    calls = `attempts + 1`), matching `PROVIDER_RETRY_ATTEMPTS`.
    """
    retrying = AsyncRetrying(
        retry=retry_if_exception(_is_transient),
        stop=stop_after_attempt(attempts + 1),
        wait=wait_exponential(multiplier=backoff_seconds),
        reraise=True,
    )
    try:
        async for attempt in retrying:
            with attempt:
                return await request()
    except httpx.TimeoutException as exc:
        raise ProviderTimeoutError(provider, f"timed out: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            provider, f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderError(provider, str(exc)) from exc

    raise AssertionError("unreachable: AsyncRetrying always returns or raises")
