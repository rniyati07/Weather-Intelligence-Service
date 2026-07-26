"""Rank days by risk and suitability -> `bestDays` / `worstDays`.

Ranking key: risk level ascending (lower risk is better), then mean
activity suitability descending (higher is better), then date ascending —
the deterministic tie-breaker, included so the result never depends on
input order or Python's sort stability. Since every day has a unique date,
this key gives a strict total order: there is always exactly one best day
and one worst day.

`bestDays`/`worstDays` are `array<date>` in the API contract (room for a
future multi-day selection); this implementation always returns exactly one
date each, chosen by the ranking above.
"""

from datetime import date

from app.domain.entities.persistence import RiskLevel
from app.domain.entities.weather_intelligence import DailyIntelligence

_RISK_ORDER: dict[RiskLevel, int] = {"low": 0, "moderate": 1, "high": 2}


def _mean_suitability(day: DailyIntelligence) -> float:
    scores = [activity.score for activity in day.activity_suitability]
    return sum(scores) / len(scores) if scores else 0.0


def _rank_key(day: DailyIntelligence) -> tuple[int, float, date]:
    return (_RISK_ORDER[day.risk_assessment.overall_risk_level], -_mean_suitability(day), day.date)


def rank_days(days: list[DailyIntelligence]) -> tuple[list[date], list[date]]:
    """Return `(best_days, worst_days)`, each a single-date list (empty if `days` is empty)."""
    if not days:
        return [], []
    ranked = sorted(days, key=_rank_key)
    return [ranked[0].date], [ranked[-1].date]
