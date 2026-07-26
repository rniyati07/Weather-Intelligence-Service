"""Trip-level rollups: `overallRiskLevel`, `tripSuitabilityScore`, `travelConfidence`.

`travelConfidence` follows TRD §7.5's contract exactly: a deterministic pure
function of three inputs — forecast horizon, inter-source agreement, and
mean data completeness — combined via weights held in rule config, never
hardcoded (the exact combination is explicitly left to implementation/config
by the TRD). This project's provider registry (Phase 5) returns one
provider's result per fetch, so in practice `provider_agreement_factor` is
almost always the config's `single_provider_neutral_factor`; the parameter
exists so this function genuinely accepts and uses all three inputs, ready
for a future multi-provider comparison without a signature change.
"""

from datetime import date

from app.domain.entities.persistence import RiskLevel
from app.domain.entities.weather_intelligence import DailyIntelligence
from app.domain.rules.config import RuleConfig

_RISK_ORDER: dict[RiskLevel, int] = {"low": 0, "moderate": 1, "high": 2}
_RISK_BY_ORDER: dict[int, RiskLevel] = {0: "low", 1: "moderate", 2: "high"}

_MIN_SCORE = 0
_MAX_SCORE = 100
_MIN_CONFIDENCE = 0.0
_MAX_CONFIDENCE = 1.0


def overall_risk_level(days: list[DailyIntelligence]) -> RiskLevel:
    """Worst-case: the maximum risk level across all days (`low` if there are none)."""
    if not days:
        return "low"
    worst_order = max(_RISK_ORDER[day.risk_assessment.overall_risk_level] for day in days)
    return _RISK_BY_ORDER[worst_order]


def trip_suitability_score(days: list[DailyIntelligence]) -> int:
    """Mean of each day's mean activity suitability, rounded and clamped to `0-100`."""
    if not days:
        return 0
    daily_means = []
    for day in days:
        scores = [activity.score for activity in day.activity_suitability]
        daily_means.append(sum(scores) / len(scores) if scores else 0.0)
    average = sum(daily_means) / len(daily_means)
    return max(_MIN_SCORE, min(_MAX_SCORE, round(average)))


def _horizon_factor(days_out: int, max_horizon_days: int) -> float:
    """1.0 at zero (or negative) days out, decaying linearly to 0.0 at `max_horizon_days`."""
    if max_horizon_days <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (days_out / max_horizon_days)))


def travel_confidence(
    *,
    reading_dates: list[date],
    as_of: date,
    mean_completeness: float,
    provider_agreement_factor: float,
    config: RuleConfig,
) -> float:
    """Combine forecast horizon, inter-source agreement, and completeness into `0.0-1.0`.

    - **Horizon**: mean of each day's `_horizon_factor((date - as_of).days, ...)` —
      further-out days lower it.
    - **Agreement**: supplied by the caller — the config's
      `single_provider_neutral_factor` when only one provider returned data
      (the current, single-fetch-per-request norm), or a real
      disagreement-derived score if a future phase compares providers.
    - **Completeness**: `mean_completeness` directly (already `0.0-1.0` from
      normalization; missing fields lower it).
    """
    weights = config.confidence_weights
    if reading_dates:
        horizon_factor = sum(
            _horizon_factor((d - as_of).days, weights.max_horizon_days) for d in reading_dates
        ) / len(reading_dates)
    else:
        horizon_factor = 0.0

    combined = (
        weights.horizon_weight * horizon_factor
        + weights.agreement_weight * provider_agreement_factor
        + weights.completeness_weight * mean_completeness
    )
    return max(_MIN_CONFIDENCE, min(_MAX_CONFIDENCE, combined))
