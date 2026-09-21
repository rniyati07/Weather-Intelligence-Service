"""Rank days by risk, suitability, and rain chance -> `bestDays` / `worstDays`.

Ranking key: risk level ascending (lower risk is better), then mean activity
suitability descending (higher is better), then precipitation probability
ascending (drier is better), then date ascending as the final deterministic
tie-breaker — included so the result never depends on input order or
Python's sort stability. Since every day has a unique date, this key gives a
strict total order: there is always exactly one best day and one worst day.

The precipitation step exists because risk level and mean suitability can
both legitimately tie across an entire short trip — live-observed: a
same-region rule config gave every day of a 4-day trip the identical
"moderate" risk and the identical per-activity suitability scores, even
though rain chance ranged from 12% to 41% across those same days. Falling
straight through to the date tie-break in that case picked day 1 as "best"
and the last day as "worst" for no reason but list position — coincidentally
the *rainiest* day was also day 1, so the assistant told a user a shower-risk
day was their best hiking day. Precipitation is the one weather signal that
is almost always independently informative even when the coarser risk/
suitability scores are not, so it goes ahead of the date fallback rather than
after it.

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


def _rank_key(day: DailyIntelligence) -> tuple[int, float, float, date]:
    return (
        _RISK_ORDER[day.risk_assessment.overall_risk_level],
        -_mean_suitability(day),
        day.summary.precipitation_probability,
        day.date,
    )


def rank_days(days: list[DailyIntelligence]) -> tuple[list[date], list[date]]:
    """Return `(best_days, worst_days)`, each a single-date list (empty if `days` is empty)."""
    if not days:
        return [], []
    ranked = sorted(days, key=_rank_key)
    return [ranked[0].date], [ranked[-1].date]
