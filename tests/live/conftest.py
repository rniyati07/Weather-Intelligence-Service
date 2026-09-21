"""Fixtures for the live smoke suite — see `tests/live/README.md`.

Unlike `tests/api/conftest.py`, nothing here is overridden: the real
`Settings`, the real database session, the real provider registry, the real
LLM client. `ASGITransport` still avoids needing a separately running
`uvicorn` process, but every request it drives reaches the actual external
services `.env` is configured for.
"""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.config.settings import get_settings

#: `pyproject.toml`'s CI placeholder — a real dev `.env` never has this
#: value, so its presence means "not really configured for live calls".
_CI_PLACEHOLDER_BASE_URL = "http://localhost/v1"


def _real_settings_configured() -> bool:
    try:
        settings = get_settings()
    except Exception:  # noqa: BLE001 - any construction failure means "not configured"
        return False
    return settings.llm_base_url != _CI_PLACEHOLDER_BASE_URL


collect_ignore_glob: list[str] = []
if not _real_settings_configured():
    # Skip collection entirely rather than erroring: importing `app.main`
    # below would otherwise raise the same "missing environment variable"
    # RuntimeError `Settings()` raises everywhere else in this codebase.
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture
def app() -> Any:
    if not _real_settings_configured():
        pytest.skip("live suite requires a real .env — see tests/live/README.md")
    from app.main import create_app

    return create_app()


@pytest_asyncio.fixture
async def client(app: Any) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", timeout=90.0
    ) as async_client:
        yield async_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().api_keys[0]}


@pytest.fixture
def ops_headers() -> dict[str, str]:
    return {"X-API-Key": get_settings().ops_api_keys[0]}
