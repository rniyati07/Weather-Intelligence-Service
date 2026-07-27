"""`WeatherIntelligence` and everything it is built from (API Spec §9.1-9.5).

Field-for-field mirrors of the API contract, kept as plain framework-free
dataclasses per §3.2 (camelCase aliasing happens at the HTTP schema layer,
Phase 9 — these are internal, snake_case). `build_weather_intelligence` at
the bottom of this module is the "Intelligence Builder" the guide's Phase 7
pipeline diagram ends with; it orchestrates the insight and recommendation
engines but never calls AI — `narrative` is always `None` here.
"""

from dataclasses import dataclass
from datetime import date

from app.domain.entities.persistence import RiskLevel, TravelAdvisory
from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.rules.config import ActivityCategory, RiskFactorType, RuleConfig, Severity


@dataclass(frozen=True, slots=True)
class ResolvedLocation:
    """The location shown on a `WeatherIntelligence` response (API Spec §9.2).

    Distinct from `domain.entities.persistence.Location`, which is a
    DB-row-shaped record keyed by an integer id and `normalized_key`; this is
    a response-facing value object keyed by the canonical `"lat,lon"` string.
    """

    id: str
    latitude: float
    longitude: float
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Period:
    """A requested, inclusive date range (API Spec §9.3)."""

    start_date: date
    end_date: date


@dataclass(frozen=True, slots=True)
class DailySummary:
    """API Spec §9.4.1."""

    temp_min_c: float
    temp_max_c: float
    precipitation_probability: float
    wind_speed_kph: float
    condition: WeatherCondition


@dataclass(frozen=True, slots=True)
class RiskFactor:
    """One contributing risk factor, always traceable to the rule that fired it.

    `rule` is the explainability anchor (NFR-1, API Spec §9.4.3): every
    `RiskFactor` a test or a consumer inspects must resolve back to exactly
    one rule id from `domain/engines/insight/rules.py`.
    """

    type: RiskFactorType
    severity: Severity
    description: str
    rule: str


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """API Spec §9.4.2."""

    overall_risk_level: RiskLevel
    risk_factors: list[RiskFactor]


@dataclass(frozen=True, slots=True)
class ActivitySuitability:
    """API Spec §9.4.4."""

    activity: ActivityCategory
    score: int


@dataclass(frozen=True, slots=True)
class DailyIntelligence:
    """One day's complete computed intelligence (API Spec §9.4)."""

    date: date
    summary: DailySummary
    risk_assessment: RiskAssessment
    activity_suitability: list[ActivitySuitability]
    packing_recommendations: list[str]
    travel_advisory: TravelAdvisory


@dataclass(frozen=True, slots=True)
class TripSummary:
    """Trip-level rollup across the whole requested period (API Spec §9.5)."""

    best_days: list[date]
    worst_days: list[date]
    overall_packing_list: list[str]
    overall_risk_level: RiskLevel
    trip_suitability_score: int
    travel_confidence: float


@dataclass(frozen=True, slots=True)
class Narrative:
    """Optional AI narration attached to a `WeatherIntelligence` (API Spec §9.6).

    Populated only by a separate narration step (Phase 8's `NarrationPort`,
    wired to the API in Phase 9) — the Intelligence Builder itself never
    produces one; it always sets `WeatherIntelligence.narrative = None`.
    """

    generated_by_llm: bool
    summary_text: str
    fallback_used: bool
    model_used: str | None = None


@dataclass(frozen=True, slots=True)
class WeatherIntelligence:
    """The root payload (API Spec §9.1). `narrative` is always `None` here —
    the Intelligence Builder never calls AI; only a separate narration step
    (Phase 8/9) may populate it, on top of this same object's data.
    `rule_config_version` stamps which rule set produced this computation
    (guide §Phase 7 step 1), and is also the narration cache's version key.
    """

    location: ResolvedLocation
    period: Period
    daily_intelligence: list[DailyIntelligence]
    trip_summary: TripSummary
    rule_config_version: str
    narrative: Narrative | None = None


def build_weather_intelligence(
    *,
    location: ResolvedLocation,
    period: Period,
    readings: list[NormalizedReading],
    rule_config: RuleConfig,
    as_of: date,
    provider_agreement_factor: float | None = None,
) -> WeatherIntelligence:
    """Assemble a complete `WeatherIntelligence` from readings — the "Intelligence Builder".

    Pure: identical inputs always produce identical output. There is no
    clock call here — `as_of` (the reference point `travelConfidence`
    measures forecast horizon from) is supplied by the caller, never read
    from the system clock, so the same inputs are always byte-identical.

    Orchestrates the Insight Engine (rules -> risk -> scoring, per day) and
    the Recommendation Engine (best/worst, packing, trip scores), then
    assembles the result. `narrative` is always `None` — this builder never
    calls AI; only a later, separate narration step (Phase 8/9) may add one.

    A day in `[period.start_date, period.end_date]` with no corresponding
    reading is simply absent from `daily_intelligence` — normalization
    (Phase 6) already dropped anything invalid rather than fabricating it,
    and this builder preserves that: missing stays missing.

    Imports the engines locally (not at module level) because `risk.py`,
    `scoring.py`, `best_worst.py`, and `trip_scores.py` import entity types
    *from this module* — a module-level import here would be circular.
    """
    from app.domain.engines.insight import risk, rules, scoring
    from app.domain.engines.recommendation import best_worst, packing, trip_scores

    if provider_agreement_factor is None:
        provider_agreement_factor = rule_config.confidence_weights.single_provider_neutral_factor

    daily_intelligence: list[DailyIntelligence] = []
    for reading in sorted(readings, key=lambda r: r.date):
        triggered = rules.evaluate(reading, rule_config)
        risk_assessment = risk.assess(triggered)

        daily_intelligence.append(
            DailyIntelligence(
                date=reading.date,
                summary=DailySummary(
                    temp_min_c=reading.temp_min_c,
                    temp_max_c=reading.temp_max_c,
                    precipitation_probability=reading.precipitation_probability,
                    wind_speed_kph=reading.wind_speed_kph,
                    condition=reading.condition,
                ),
                risk_assessment=risk_assessment,
                activity_suitability=scoring.score_activities(triggered, rule_config),
                packing_recommendations=packing.daily_packing_items(triggered, rule_config),
                travel_advisory=risk.travel_advisory(risk_assessment.overall_risk_level),
            )
        )

    best_days, worst_days = best_worst.rank_days(daily_intelligence)
    overall_packing_list = packing.aggregate_packing_list(
        [day.packing_recommendations for day in daily_intelligence], rule_config
    )
    mean_completeness = (
        sum(reading.completeness for reading in readings) / len(readings) if readings else 0.0
    )

    trip_summary = TripSummary(
        best_days=best_days,
        worst_days=worst_days,
        overall_packing_list=overall_packing_list,
        overall_risk_level=trip_scores.overall_risk_level(daily_intelligence),
        trip_suitability_score=trip_scores.trip_suitability_score(daily_intelligence),
        travel_confidence=trip_scores.travel_confidence(
            reading_dates=[day.date for day in daily_intelligence],
            as_of=as_of,
            mean_completeness=mean_completeness,
            provider_agreement_factor=provider_agreement_factor,
            config=rule_config,
        ),
    )

    return WeatherIntelligence(
        location=location,
        period=period,
        daily_intelligence=daily_intelligence,
        trip_summary=trip_summary,
        rule_config_version=rule_config.version,
    )


__all__ = [
    "ActivitySuitability",
    "DailyIntelligence",
    "DailySummary",
    "Narrative",
    "Period",
    "ResolvedLocation",
    "RiskAssessment",
    "RiskFactor",
    "TripSummary",
    "WeatherIntelligence",
    "build_weather_intelligence",
]
