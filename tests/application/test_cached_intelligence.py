"""`CachedIntelligenceUseCase` — the chat-only, TTL-bound intelligence cache.

No real time.sleep in these tests: TTL behaviour is exercised by writing
directly into the backing store with a controlled `cached_at` timestamp,
not by actually waiting out a real TTL window.
"""

import time
from datetime import date

from app.application.use_cases.cached_intelligence import CachedIntelligenceUseCase
from app.application.use_cases.get_weather_intelligence import IntelligenceResult
from app.domain.entities.weather_intelligence import (
    Period,
    ResolvedLocation,
    TripSummary,
    WeatherIntelligence,
)

DAY_A = date(2026, 9, 1)
DAY_B = date(2026, 9, 2)


def _result(version: str = "v1") -> IntelligenceResult:
    intelligence = WeatherIntelligence(
        location=ResolvedLocation(id="1,1", latitude=1.0, longitude=1.0),
        period=Period(start_date=DAY_A, end_date=DAY_A),
        daily_intelligence=[],
        trip_summary=TripSummary(
            best_days=[],
            worst_days=[],
            overall_packing_list=[],
            overall_risk_level="low",
            trip_suitability_score=80,
            travel_confidence=0.9,
        ),
        rule_config_version=version,
    )
    return IntelligenceResult(
        intelligence=intelligence, readings=[], cache_status="miss", degraded=False
    )


class FakeInner:
    def __init__(self, *, rule_config_version: str = "v1") -> None:
        self.rule_config_version = rule_config_version
        self.call_count = 0

    async def execute(self, *, latitude, longitude, start, end, name=None) -> IntelligenceResult:
        self.call_count += 1
        return _result(self.rule_config_version)


async def _call(
    cache: CachedIntelligenceUseCase, *, lat: float = 1.0, lon: float = 1.0, day: date = DAY_A
) -> IntelligenceResult:
    return await cache.execute(latitude=lat, longitude=lon, start=day, end=day)


class TestCacheHitAndMiss:
    async def test_first_call_hits_the_inner_use_case(self) -> None:
        inner = FakeInner()
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store={})

        await _call(cache)

        assert inner.call_count == 1

    async def test_second_identical_call_within_ttl_does_not_hit_inner(self) -> None:
        inner = FakeInner()
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store={})

        await _call(cache)
        await _call(cache)

        assert inner.call_count == 1

    async def test_different_location_is_a_separate_cache_entry(self) -> None:
        inner = FakeInner()
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store={})

        await _call(cache, lat=1.0, lon=1.0)
        await _call(cache, lat=2.0, lon=2.0)

        assert inner.call_count == 2

    async def test_different_dates_is_a_separate_cache_entry(self) -> None:
        inner = FakeInner()
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store={})

        await _call(cache, day=DAY_A)
        await _call(cache, day=DAY_B)

        assert inner.call_count == 2

    async def test_rule_config_version_change_busts_the_cache(self) -> None:
        """Correctness guarantee: a rule change is never served stale."""
        store: dict = {}
        inner_v1 = FakeInner(rule_config_version="v1")
        cache_v1 = CachedIntelligenceUseCase(inner_v1, ttl_seconds=3600, store=store)
        await _call(cache_v1)

        inner_v2 = FakeInner(rule_config_version="v2")
        cache_v2 = CachedIntelligenceUseCase(inner_v2, ttl_seconds=3600, store=store)
        await _call(cache_v2)

        assert inner_v2.call_count == 1  # v2's own key was a miss, not reused from v1

    async def test_shared_store_is_actually_shared_across_instances(self) -> None:
        """The point of injecting `store` rather than owning it: two
        `CachedIntelligenceUseCase` instances (one per request, as DI
        constructs them) must still see each other's cached entries."""
        store: dict = {}
        inner_a = FakeInner()
        cache_a = CachedIntelligenceUseCase(inner_a, ttl_seconds=3600, store=store)
        await _call(cache_a)

        inner_b = FakeInner()
        cache_b = CachedIntelligenceUseCase(inner_b, ttl_seconds=3600, store=store)
        await _call(cache_b)

        assert inner_b.call_count == 0  # served from cache_a's entry


class TestTtlExpiry:
    async def test_expired_entry_is_not_reused(self) -> None:
        inner = FakeInner()
        store: dict = {}
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=1, store=store)
        await _call(cache)

        # Backdate the cached entry instead of a real sleep.
        key = next(iter(store))
        cached_at, result = store[key]
        store[key] = (cached_at - 10, result)

        await _call(cache)

        assert inner.call_count == 2

    async def test_fresh_entry_within_ttl_is_reused(self) -> None:
        inner = FakeInner()
        store: dict = {}
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store=store)
        await _call(cache)

        key = next(iter(store))
        cached_at, _result_value = store[key]
        assert time.monotonic() - cached_at < 3600

        await _call(cache)

        assert inner.call_count == 1


class TestProtocolCompliance:
    async def test_rule_config_version_delegates_to_inner(self) -> None:
        inner = FakeInner(rule_config_version="2026.07")
        cache = CachedIntelligenceUseCase(inner, ttl_seconds=3600, store={})

        assert cache.rule_config_version == "2026.07"
