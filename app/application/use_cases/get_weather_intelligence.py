"""`GetWeatherIntelligence` — the use case every intelligence endpoint builds on.

Acquires readings via the shared loader, runs the deterministic engines, and
persists the computed rows (guide §Phase 9 step 5). It orchestrates only:
provider selection lives in the registry (Phase 5), computation in the
engines (Phase 7), persistence behind the repository port (Phase 3).

Best-days and packing are *projections* of this same result (API Spec
§8.2/§8.3), so they reuse this use case rather than recomputing anything.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.application.use_cases.load_readings import CACHE_HIT, WeatherReadingsLoader
from app.domain.entities.persistence import DailyIntelligenceRecord
from app.domain.entities.weather import NormalizedReading
from app.domain.entities.weather_intelligence import (
    Period,
    ResolvedLocation,
    WeatherIntelligence,
    build_weather_intelligence,
)
from app.domain.ports.repository import WeatherRepository
from app.domain.rules.config import RuleConfig


@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    """Computed intelligence plus the metadata the response envelope needs."""

    intelligence: WeatherIntelligence
    readings: list[NormalizedReading]
    cache_status: str
    degraded: bool


class GetWeatherIntelligence:
    """Builds `WeatherIntelligence` for a location and inclusive date range."""

    def __init__(
        self,
        *,
        loader: WeatherReadingsLoader,
        repository: WeatherRepository,
        rule_config: RuleConfig,
        intelligence_ttl_seconds: int = 0,
    ) -> None:
        self._loader = loader
        self._repository = repository
        self._rule_config = rule_config
        # 0 disables the freshness guard below rather than treating every row
        # as fresh forever — matches "unconfigured means off", not "always".
        self._intelligence_ttl_seconds = intelligence_ttl_seconds

    @property
    def rule_config_version(self) -> str:
        """Exposed for `CachedIntelligenceUseCase`'s cache key — the rule
        version isn't known to a caller until after a call completes
        otherwise, and a cache key must be computable before that."""
        return self._rule_config.version

    async def execute(
        self, *, latitude: float, longitude: float, start: date, end: date, name: str | None = None
    ) -> IntelligenceResult:
        loaded = await self._loader.load(
            latitude=latitude, longitude=longitude, start=start, end=end, name=name
        )

        intelligence = build_weather_intelligence(
            location=ResolvedLocation(
                id=f"{latitude},{longitude}",
                latitude=latitude,
                longitude=longitude,
                name=name,
            ),
            period=Period(start_date=start, end_date=end),
            readings=loaded.readings,
            rule_config=self._rule_config,
            # The engines take no clock of their own (Phase 7); the reference
            # point for forecast horizon is supplied here, by the caller.
            as_of=datetime.now(UTC).date(),
        )

        # Only persist when something was actually recomputed from new data —
        # a cache hit would just rewrite identical deterministic rows.
        if loaded.cache_status != CACHE_HIT:
            await self._persist_intelligence(loaded.location_id, intelligence)

        return IntelligenceResult(
            intelligence=intelligence,
            readings=loaded.readings,
            cache_status=loaded.cache_status,
            degraded=loaded.degraded,
        )

    async def _persist_intelligence(
        self, location_id: int, intelligence: WeatherIntelligence
    ) -> None:
        """Store computed rows stamped with the rule version behind them.

        Guarded by `get_fresh_intelligence` (previously dormant — wired here
        per the approved freshness decision): a day whose row is already
        fresh, for this exact rule version, is skipped rather than
        re-inserted. Full reconstruction of `WeatherIntelligence` straight
        from stored rows was evaluated and rejected — `DailyIntelligenceRecord`
        does not persist the daily weather summary (temps, precipitation,
        condition), only the computed risk/activity/packing fields, so there
        is nothing to hydrate `DailySummary` from without a schema change.
        Rule evaluation itself is pure, in-process, and negligible cost; the
        actual problem this fixes is unbounded duplicate-row growth on every
        turn that touches any day in an already-fresh range, not recompute
        latency.
        """
        already_fresh_dates: set[date] = set()
        if self._intelligence_ttl_seconds > 0 and intelligence.daily_intelligence:
            fresh_since = datetime.now(UTC) - timedelta(seconds=self._intelligence_ttl_seconds)
            existing = await self._repository.get_fresh_intelligence(
                location_id=location_id,
                start_date=intelligence.period.start_date,
                end_date=intelligence.period.end_date,
                rule_config_version=intelligence.rule_config_version,
                fresh_since=fresh_since,
            )
            already_fresh_dates = {row.date for row in existing}

        generated_at = datetime.now(UTC)
        for day in intelligence.daily_intelligence:
            if day.date in already_fresh_dates:
                continue
            await self._repository.save_intelligence(
                DailyIntelligenceRecord(
                    location_id=location_id,
                    date=day.date,
                    risk_level=day.risk_assessment.overall_risk_level,
                    risk_factors=[
                        {
                            "type": factor.type,
                            "severity": factor.severity,
                            "description": factor.description,
                            "rule": factor.rule,
                        }
                        for factor in day.risk_assessment.risk_factors
                    ],
                    activity_scores={a.activity: a.score for a in day.activity_suitability},
                    packing=list(day.packing_recommendations),
                    travel_advisory=day.travel_advisory,
                    rule_config_version=intelligence.rule_config_version,
                    generated_at=generated_at,
                )
            )
