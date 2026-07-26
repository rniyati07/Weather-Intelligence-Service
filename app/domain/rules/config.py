"""Typed rule configuration: every threshold, weight, and packing rule the
Insight and Recommendation engines read from — never a literal in
`domain/engines/`.

`parse_rule_config` is a pure function: it turns an already-loaded mapping
(read from YAML by `infrastructure/config/rule_config_loader.py`) into a
validated, immutable `RuleConfig`. It performs no file I/O itself — that
would violate domain purity — it only validates and shapes data it is
handed.
"""

from dataclasses import dataclass
from typing import Any, Literal, cast, get_args

#: Stable identifier stamped onto every computed row/response so a rule
#: change is auditable (guide §4.1 `RULE_CONFIG_VERSION`).
RULE_CONFIG_VERSION = "2026.07"

# Shared vocabulary (API Spec §10) used by both this config schema (as dict
# keys) and the engines (`domain/engines/insight/*`). Defined here, not in
# `domain/entities/weather_intelligence.py`, so the engines can depend on
# these types without that module's builder — which depends on the engines
# for orchestration — creating a circular import.
RiskFactorType = Literal["heat", "cold", "rain", "storm", "wind"]
ActivityCategory = Literal["outdoor_sightseeing", "beach", "indoor_museum"]
Severity = Literal["low", "moderate", "high"]

_RISK_FACTOR_TYPES = frozenset(get_args(RiskFactorType))
_ACTIVITY_CATEGORIES = frozenset(get_args(ActivityCategory))


class RuleConfigError(ValueError):
    """Raised when rule configuration data is missing, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class HeatThresholds:
    moderate_temp_max_c: float
    high_temp_max_c: float


@dataclass(frozen=True, slots=True)
class ColdThresholds:
    moderate_temp_min_c: float
    high_temp_min_c: float


@dataclass(frozen=True, slots=True)
class RainThresholds:
    moderate_precip_probability: float
    high_precip_probability: float


@dataclass(frozen=True, slots=True)
class WindThresholds:
    moderate_wind_speed_kph: float
    high_wind_speed_kph: float


@dataclass(frozen=True, slots=True)
class InsightThresholds:
    """Numeric cutoffs `engines/insight/rules.py` evaluates readings against."""

    heat: HeatThresholds
    cold: ColdThresholds
    rain: RainThresholds
    wind: WindThresholds


@dataclass(frozen=True, slots=True)
class ActivityScoringRule:
    """One `ActivityCategory`'s base score and per-risk-factor-type adjustments."""

    base_score: int
    penalties: dict[RiskFactorType, float]
    bonuses: dict[RiskFactorType, float]


@dataclass(frozen=True, slots=True)
class ConfidenceWeights:
    """Weights combining the three `travelConfidence` inputs (TRD §7.5)."""

    horizon_weight: float
    agreement_weight: float
    completeness_weight: float
    max_horizon_days: int
    single_provider_neutral_factor: float


@dataclass(frozen=True, slots=True)
class RuleConfig:
    """Everything the deterministic engines need, versioned as one unit."""

    version: str
    insight_thresholds: InsightThresholds
    activity_scoring: dict[ActivityCategory, ActivityScoringRule]
    packing_rules: dict[RiskFactorType, list[str]]
    packing_item_order: list[str]
    confidence_weights: ConfidenceWeights


def _require(data: dict[str, Any], key: str, *, context: str) -> Any:
    if key not in data:
        raise RuleConfigError(f"missing '{key}' in {context}")
    return data[key]


def _parse_heat(data: dict[str, Any]) -> HeatThresholds:
    context = "insight_thresholds.heat"
    return HeatThresholds(
        moderate_temp_max_c=float(_require(data, "moderate_temp_max_c", context=context)),
        high_temp_max_c=float(_require(data, "high_temp_max_c", context=context)),
    )


def _parse_cold(data: dict[str, Any]) -> ColdThresholds:
    context = "insight_thresholds.cold"
    return ColdThresholds(
        moderate_temp_min_c=float(_require(data, "moderate_temp_min_c", context=context)),
        high_temp_min_c=float(_require(data, "high_temp_min_c", context=context)),
    )


def _parse_rain(data: dict[str, Any]) -> RainThresholds:
    return RainThresholds(
        moderate_precip_probability=float(
            _require(data, "moderate_precip_probability", context="insight_thresholds.rain")
        ),
        high_precip_probability=float(
            _require(data, "high_precip_probability", context="insight_thresholds.rain")
        ),
    )


def _parse_wind(data: dict[str, Any]) -> WindThresholds:
    return WindThresholds(
        moderate_wind_speed_kph=float(
            _require(data, "moderate_wind_speed_kph", context="insight_thresholds.wind")
        ),
        high_wind_speed_kph=float(
            _require(data, "high_wind_speed_kph", context="insight_thresholds.wind")
        ),
    )


def _parse_insight_thresholds(data: dict[str, Any]) -> InsightThresholds:
    return InsightThresholds(
        heat=_parse_heat(_require(data, "heat", context="insight_thresholds")),
        cold=_parse_cold(_require(data, "cold", context="insight_thresholds")),
        rain=_parse_rain(_require(data, "rain", context="insight_thresholds")),
        wind=_parse_wind(_require(data, "wind", context="insight_thresholds")),
    )


def _parse_activity_scoring(data: dict[str, Any]) -> dict[ActivityCategory, ActivityScoringRule]:
    missing = _ACTIVITY_CATEGORIES - data.keys()
    if missing:
        raise RuleConfigError(f"activity_scoring is missing categories: {sorted(missing)}")

    scoring: dict[ActivityCategory, ActivityScoringRule] = {}
    for category, rule_data in data.items():
        if category not in _ACTIVITY_CATEGORIES:
            continue  # forward-compatible: unknown categories are additive, per API Spec §12
        base_score = int(_require(rule_data, "base_score", context=f"activity_scoring.{category}"))
        if not (0 <= base_score <= 100):
            raise RuleConfigError(f"activity_scoring.{category}.base_score must be within 0-100")
        scoring[cast(ActivityCategory, category)] = ActivityScoringRule(
            base_score=base_score,
            penalties=dict(rule_data.get("penalties", {})),
            bonuses=dict(rule_data.get("bonuses", {})),
        )
    return scoring


def _parse_packing_rules(data: dict[str, Any]) -> dict[RiskFactorType, list[str]]:
    unknown = data.keys() - _RISK_FACTOR_TYPES
    if unknown:
        raise RuleConfigError(f"packing_rules has unknown risk factor types: {sorted(unknown)}")
    return {cast(RiskFactorType, factor_type): list(items) for factor_type, items in data.items()}


def _parse_confidence_weights(data: dict[str, Any]) -> ConfidenceWeights:
    horizon_weight = float(_require(data, "horizon_weight", context="confidence"))
    agreement_weight = float(_require(data, "agreement_weight", context="confidence"))
    completeness_weight = float(_require(data, "completeness_weight", context="confidence"))

    total = horizon_weight + agreement_weight + completeness_weight
    if abs(total - 1.0) > 1e-6:
        raise RuleConfigError(f"confidence weights must sum to 1.0, got {total}")

    return ConfidenceWeights(
        horizon_weight=horizon_weight,
        agreement_weight=agreement_weight,
        completeness_weight=completeness_weight,
        max_horizon_days=int(_require(data, "max_horizon_days", context="confidence")),
        single_provider_neutral_factor=float(
            _require(data, "single_provider_neutral_factor", context="confidence")
        ),
    )


def parse_rule_config(data: dict[str, Any]) -> RuleConfig:
    """Validate and shape already-loaded rule config data into a `RuleConfig`.

    Raises `RuleConfigError` naming the missing/invalid field on any problem.
    """
    version = str(_require(data, "version", context="rule config"))

    packing_item_order = list(_require(data, "packing_item_order", context="rule config"))

    return RuleConfig(
        version=version,
        insight_thresholds=_parse_insight_thresholds(
            _require(data, "insight_thresholds", context="rule config")
        ),
        activity_scoring=_parse_activity_scoring(
            _require(data, "activity_scoring", context="rule config")
        ),
        packing_rules=_parse_packing_rules(_require(data, "packing_rules", context="rule config")),
        packing_item_order=packing_item_order,
        confidence_weights=_parse_confidence_weights(
            _require(data, "confidence", context="rule config")
        ),
    )
