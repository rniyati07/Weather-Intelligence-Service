"""Tests for the shared provider HTTP plumbing: retry, timeout, and error translation.

Covered once here rather than duplicated per adapter, since every adapter
goes through the same `call_with_retry` helper.
"""

import httpx
import pytest
import respx

from app.infrastructure.providers.base import (
    USER_AGENT,
    ProviderError,
    ProviderTimeoutError,
    build_http_client,
    call_with_retry,
)

_URL = "https://example-provider.test/data"


class TestCallWithRetry:
    @respx.mock
    async def test_success_returns_response(self) -> None:
        respx.get(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        async with httpx.AsyncClient() as client:

            async def request() -> httpx.Response:
                response = await client.get(_URL)
                response.raise_for_status()
                return response

            response = await call_with_retry(
                request, provider="test", attempts=2, backoff_seconds=0.01
            )

        assert response.json() == {"ok": True}

    @respx.mock
    async def test_4xx_does_not_retry(self) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(400, json={"error": "bad"}))

        async with httpx.AsyncClient() as client:

            async def request() -> httpx.Response:
                response = await client.get(_URL)
                response.raise_for_status()
                return response

            with pytest.raises(ProviderError):
                await call_with_retry(request, provider="test", attempts=2, backoff_seconds=0.01)

        assert route.call_count == 1

    @respx.mock
    async def test_5xx_retries_then_raises(self) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(500))

        async with httpx.AsyncClient() as client:

            async def request() -> httpx.Response:
                response = await client.get(_URL)
                response.raise_for_status()
                return response

            with pytest.raises(ProviderError):
                await call_with_retry(request, provider="test", attempts=2, backoff_seconds=0.01)

        assert route.call_count == 3  # 1 initial attempt + 2 retries

    @respx.mock
    async def test_timeout_raises_provider_timeout_error(self) -> None:
        respx.get(_URL).mock(side_effect=httpx.TimeoutException("timed out"))

        async with httpx.AsyncClient() as client:

            async def request() -> httpx.Response:
                return await client.get(_URL)

            with pytest.raises(ProviderTimeoutError):
                await call_with_retry(request, provider="test", attempts=1, backoff_seconds=0.01)

    @respx.mock
    async def test_connect_error_retries_then_raises(self) -> None:
        route = respx.get(_URL).mock(side_effect=httpx.ConnectError("refused"))

        async with httpx.AsyncClient() as client:

            async def request() -> httpx.Response:
                return await client.get(_URL)

            with pytest.raises(ProviderError):
                await call_with_retry(request, provider="test", attempts=2, backoff_seconds=0.01)

        assert route.call_count == 3


class TestUserAgent:
    """Every outbound provider call must identify the client.

    Overpass rejects httpx's default `python-httpx/...` agent with a bare
    `406 Not Acceptable`, which surfaced as "this trip has no attractions"
    on every chat turn rather than as an error — so the header is load-
    bearing, not decoration.
    """

    def test_client_sends_an_identifying_user_agent(self) -> None:
        client = build_http_client(5.0)

        assert client.headers["user-agent"] == USER_AGENT
        assert "httpx" not in client.headers["user-agent"].lower()

    @respx.mock
    async def test_user_agent_reaches_the_provider(self) -> None:
        route = respx.get(_URL).mock(return_value=httpx.Response(200, json={"ok": True}))

        client = build_http_client(5.0)
        await client.get(_URL)

        assert route.calls.last.request.headers["user-agent"] == USER_AGENT
