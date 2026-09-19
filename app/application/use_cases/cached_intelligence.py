"""A tiny in-process memoization of `GetWeatherIntelligence.execute()`,
used only by the chat path.

Not a caching subsystem: same size and shape as `NarrationService`'s own
in-process cache (Phase 8, already shipped) — a plain dict, no LRU, no
external store, no new infrastructure. REST weather/narrative endpoints keep
calling `GetWeatherIntelligence` directly through `WeatherIntelligenceUseCaseDep`,
completely unaffected; this wrapper is only ever reached from
`ChatOrchestratorDep`.

Why chat specifically needs this and REST doesn't: a REST client asks once
and gets one answer. A chat conversation asks the same underlying question
("what's the weather for Goa, Aug 20-23?") on every follow-up turn — "which
day is best for beaches?", "what if it rains?" — each a separate HTTP
request with a fresh `GetWeatherIntelligence` instance, so nothing upstream
already remembers the answer.

Correctness bound: the cache TTL is `PROVIDER_CACHE_TTL_SECONDS` — the exact
setting `WeatherReadingsLoader` already uses to decide whether a *raw
reading* is still fresh. This cache can therefore never present intelligence
as current for longer than the readings it was built from are themselves
already considered current — no new staleness window is introduced, only
reuse within a window the system already relies on. The rule config version
is part of the cache key, so a rule change is never served stale.
"""

import time
from datetime import date
from typing import Protocol

from app.application.use_cases.get_weather_intelligence import IntelligenceResult


class IntelligenceUseCase(Protocol):
    """What `ChatOrchestrator` needs from an intelligence use case — not the
    concrete `GetWeatherIntelligence` class. Mirrors `narration_service.py`'s
    `LlmClientProtocol`: both `GetWeatherIntelligence` and
    `CachedIntelligenceUseCase` satisfy this structurally.

    `rule_config_version` is part of the contract, not just an
    implementation detail of `GetWeatherIntelligence` — any use case that
    can build weather intelligence has a rule version behind it, and the
    cache key needs to read it without knowing which implementation it has.
    """

    @property
    def rule_config_version(self) -> str: ...

    async def execute(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> IntelligenceResult: ...


CacheKey = tuple[float, float, str, str, str]


class CachedIntelligenceUseCase:
    """Wraps a real `IntelligenceUseCase`; memoizes by
    `(lat, lon, start, end, rule_config_version)` for `ttl_seconds`.

    `store` is injected rather than owned, so the backing dict can be a
    process-wide singleton (`get_chat_intelligence_cache_store`) shared
    across the per-request instances DI constructs — the cache would be
    useless if it only lived as long as one request's dependency graph.
    """

    def __init__(
        self,
        inner: IntelligenceUseCase,
        *,
        ttl_seconds: int,
        store: dict[CacheKey, tuple[float, IntelligenceResult]],
    ) -> None:
        self._inner = inner
        self._ttl_seconds = ttl_seconds
        self._store = store

    @property
    def rule_config_version(self) -> str:
        return self._inner.rule_config_version

    async def execute(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> IntelligenceResult:
        key: CacheKey = (
            round(latitude, 4),
            round(longitude, 4),
            start.isoformat(),
            end.isoformat(),
            self._inner.rule_config_version,
        )

        cached = self._store.get(key)
        if cached is not None:
            cached_at, result = cached
            if time.monotonic() - cached_at < self._ttl_seconds:
                return result

        result = await self._inner.execute(
            latitude=latitude, longitude=longitude, start=start, end=end, name=name
        )
        self._store[key] = (time.monotonic(), result)
        return result


__all__ = ["CacheKey", "CachedIntelligenceUseCase", "IntelligenceUseCase"]
