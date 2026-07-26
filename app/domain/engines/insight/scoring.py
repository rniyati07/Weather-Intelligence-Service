"""Per-`ActivityCategory` suitability scoring: base score + config-driven adjustments.

For each triggered `RiskFactorType`, the day's *worst* severity determines a
multiplier (1x moderate, 2x high) applied to that activity's configured
penalty/bonus for the type. Purely arithmetic: same inputs always produce
the same score, clamped to `0-100` and rounded with banker's-unbiased
`round()` (Python's default), so output never depends on anything but the
triggered rules and the config.
"""

from app.domain.engines.insight.rules import TriggeredRule
from app.domain.entities.weather_intelligence import ActivitySuitability
from app.domain.rules.config import RiskFactorType, RuleConfig, Severity

_SEVERITY_ORDER: dict[Severity, int] = {"low": 0, "moderate": 1, "high": 2}
_HIGH_SEVERITY_MULTIPLIER = 2
_MODERATE_SEVERITY_MULTIPLIER = 1
_MIN_SCORE = 0
_MAX_SCORE = 100


def _worst_severity_by_type(triggered: list[TriggeredRule]) -> dict[RiskFactorType, Severity]:
    worst: dict[RiskFactorType, Severity] = {}
    for rule in triggered:
        current = worst.get(rule.factor_type)
        if current is None or _SEVERITY_ORDER[rule.severity] > _SEVERITY_ORDER[current]:
            worst[rule.factor_type] = rule.severity
    return worst


def score_activities(
    triggered: list[TriggeredRule], config: RuleConfig
) -> list[ActivitySuitability]:
    """Score every configured `ActivityCategory` for one day's triggered rules."""
    worst_by_type = _worst_severity_by_type(triggered)

    scores: list[ActivitySuitability] = []
    for activity, rule in config.activity_scoring.items():
        score = float(rule.base_score)
        for factor_type, severity in worst_by_type.items():
            multiplier = (
                _HIGH_SEVERITY_MULTIPLIER
                if severity == "high"
                else _MODERATE_SEVERITY_MULTIPLIER
            )
            score -= rule.penalties.get(factor_type, 0.0) * multiplier
            score += rule.bonuses.get(factor_type, 0.0) * multiplier

        clamped = max(_MIN_SCORE, min(_MAX_SCORE, round(score)))
        scores.append(ActivitySuitability(activity=activity, score=clamped))

    return scores
