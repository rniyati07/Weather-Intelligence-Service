"""Shared fixtures for the domain engine test suite.

`rule_config` builds a `RuleConfig` from a dict this test suite owns —
deliberately not loaded from the production YAML, so tuning a real
threshold later doesn't silently change dozens of test expectations here.
The numbers mirror `infrastructure/config/rule_config/2026.07.yaml` at the
time of writing, but the two are intentionally decoupled.
"""

from datetime import date
from typing import Any

import pytest

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.rules.config import RuleConfig, parse_rule_config

_RULE_CONFIG_DATA: dict[str, Any] = {
    "version": "test-2026.07",
    "insight_thresholds": {
        "heat": {"moderate_temp_max_c": 30.0, "high_temp_max_c": 35.0},
        "cold": {"moderate_temp_min_c": 10.0, "high_temp_min_c": 5.0},
        "rain": {"moderate_precip_probability": 0.6, "high_precip_probability": 0.8},
        "wind": {"moderate_wind_speed_kph": 25.0, "high_wind_speed_kph": 40.0},
    },
    "activity_scoring": {
        "outdoor_sightseeing": {
            "base_score": 80,
            "penalties": {"rain": 30, "storm": 50, "wind": 20, "heat": 15, "cold": 15},
            "bonuses": {},
        },
        "beach": {
            "base_score": 70,
            "penalties": {"rain": 40, "storm": 60, "wind": 15, "cold": 30},
            "bonuses": {"heat": 10},
        },
        "indoor_museum": {
            "base_score": 60,
            "penalties": {"storm": 5},
            "bonuses": {"rain": 20, "heat": 5},
        },
    },
    "packing_rules": {
        "rain": ["waterproof jacket", "quick-dry footwear"],
        "storm": ["waterproof jacket"],
        "heat": ["sunscreen", "light cottons"],
        "cold": ["warm layers"],
        "wind": ["windbreaker"],
    },
    "packing_item_order": [
        "waterproof jacket",
        "windbreaker",
        "warm layers",
        "light cottons",
        "sunscreen",
        "quick-dry footwear",
    ],
    "confidence": {
        "horizon_weight": 0.4,
        "agreement_weight": 0.2,
        "completeness_weight": 0.4,
        "max_horizon_days": 16,
        "single_provider_neutral_factor": 0.8,
    },
}


@pytest.fixture
def rule_config() -> RuleConfig:
    return parse_rule_config(_RULE_CONFIG_DATA)


def make_reading(
    *,
    day: date = date(2026, 8, 1),
    temp_min_c: float = 20.0,
    temp_max_c: float = 25.0,
    precipitation_probability: float = 0.1,
    wind_speed_kph: float = 10.0,
    condition: WeatherCondition = WeatherCondition.CLEAR,
    completeness: float = 1.0,
    source_class: str = "forecast",
    precipitation_mm: float | None = None,
    humidity: float | None = None,
) -> NormalizedReading:
    """A `NormalizedReading` with clear-day defaults; override only what a test needs."""
    return NormalizedReading(
        date=day,
        temp_min_c=temp_min_c,
        temp_max_c=temp_max_c,
        precipitation_probability=precipitation_probability,
        wind_speed_kph=wind_speed_kph,
        condition=condition,
        completeness=completeness,
        source_class=source_class,  # type: ignore[arg-type]
        precipitation_mm=precipitation_mm,
        humidity=humidity,
    )
