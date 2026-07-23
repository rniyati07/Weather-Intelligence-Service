"""Tests for the shared provider HTTP plumbing: retry, timeout, and error translation.

Covered once here rather than duplicated per adapter, since every adapter
goes through the same `call_with_retry` helper.
"""

import httpx
import pytest
import respx

from app.infrastructure.providers.base import ProviderError, ProviderTimeoutError, call_with_retry

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
