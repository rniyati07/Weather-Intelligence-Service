"""Triggered rules -> `RiskAssessment`, and `RiskLevel` -> `TravelAdvisory`.

`RiskLevel` is the maximum severity among a day's triggered rules — no
triggered rules means "low", the baseline. `TravelAdvisory` is a fixed
mapping from `RiskLevel` (API Spec §10): this is part of the contract
itself, not a tunable business threshold, so it is not read from rule
config.
"""

from app.domain.engines.insight.rules import TriggeredRule
from app.domain.entities.persistence import RiskLevel, TravelAdvisory
from app.domain.entities.weather_intelligence import RiskAssessment, RiskFactor
from app.domain.rules.config import Severity

_SEVERITY_ORDER: dict[Severity, int] = {"low": 0, "moderate": 1, "high": 2}

_ADVISORY_BY_RISK_LEVEL: dict[RiskLevel, TravelAdvisory] = {
    "low": "proceed",
    "moderate": "caution",
    "high": "avoid",
}


def _overall_risk_level(triggered: list[TriggeredRule]) -> RiskLevel:
    if not triggered:
        return "low"
    worst = max(triggered, key=lambda t: _SEVERITY_ORDER[t.severity])
    return worst.severity


def assess(triggered: list[TriggeredRule]) -> RiskAssessment:
    """Build the day's `RiskAssessment` from its triggered rules."""
    risk_factors = [
        RiskFactor(
            type=t.factor_type, severity=t.severity, description=t.description, rule=t.rule_id
        )
        for t in triggered
    ]
    return RiskAssessment(
        overall_risk_level=_overall_risk_level(triggered), risk_factors=risk_factors
    )


def travel_advisory(risk_level: RiskLevel) -> TravelAdvisory:
    """Day risk -> advisory: `low` -> `proceed`, `moderate` -> `caution`, `high` -> `avoid`."""
    return _ADVISORY_BY_RISK_LEVEL[risk_level]
