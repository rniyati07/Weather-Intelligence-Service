"""Integration tests for `build_weather_intelligence` — the Intelligence Builder.

Covers what only makes sense at the whole-pipeline level: determinism
(100 runs, byte-identical), explainability (every `RiskFactor.rule` traces
to a known rule), and golden-file regression (any drift in the deterministic
core fails the build).
"""

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from app.domain.engines.insight.rules import KNOWN_RULE_IDS
from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.entities.weather_intelligence import (
    Period,
    ResolvedLocation,
    WeatherIntelligence,
    build_weather_intelligence,
)
from app.domain.rules.config import RuleConfig

_GOLDEN_DIR = Path(__file__).parent / "golden"

_LOCATION = ResolvedLocation(id="15.25,74.125", latitude=15.25, longitude=74.125, name="Goa")
_PERIOD = Period(start_date=date(2026, 8, 1), end_date=date(2026, 8, 2))
_AS_OF = date(2026, 7, 26)

_STORM_READING = NormalizedReading(
    date=date(2026, 8, 1),
    temp_min_c=24.0,
    temp_max_c=36.0,
    precipitation_probability=0.9,
    wind_speed_kph=45.0,
    condition=WeatherCondition.THUNDERSTORM,
    completeness=1.0,
    source_class="forecast",
    precipitation_mm=20.0,
    humidity=0.9,
)
_CLEAR_READING = NormalizedReading(
    date=date(2026, 8, 2),
    temp_min_c=20.0,
    temp_max_c=27.0,
    precipitation_probability=0.05,
    wind_speed_kph=10.0,
    condition=WeatherCondition.CLEAR,
    completeness=0.5,
    source_class="forecast",
)


def _to_json_safe(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_json_safe(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, list):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_json_safe(v) for k, v in obj.items()}
    return obj


def _build(rule_config: RuleConfig) -> WeatherIntelligence:
    return build_weather_intelligence(
        location=_LOCATION,
        period=_PERIOD,
        readings=[_STORM_READING, _CLEAR_READING],
        rule_config=rule_config,
        as_of=_AS_OF,
    )


class TestDeterminism:
    def test_same_input_run_100_times_is_byte_identical(self, rule_config: RuleConfig) -> None:
        first = json.dumps(_to_json_safe(_build(rule_config)), sort_keys=True)
        for _ in range(100):
            assert json.dumps(_to_json_safe(_build(rule_config)), sort_keys=True) == first

    def test_reading_order_does_not_affect_output(self, rule_config: RuleConfig) -> None:
        forward = build_weather_intelligence(
            location=_LOCATION,
            period=_PERIOD,
            readings=[_STORM_READING, _CLEAR_READING],
            rule_config=rule_config,
            as_of=_AS_OF,
        )
        reversed_order = build_weather_intelligence(
            location=_LOCATION,
            period=_PERIOD,
            readings=[_CLEAR_READING, _STORM_READING],
            rule_config=rule_config,
            as_of=_AS_OF,
        )
        assert _to_json_safe(forward) == _to_json_safe(reversed_order)


class TestExplainability:
    def test_every_risk_factor_has_a_non_empty_known_rule_id(
        self, rule_config: RuleConfig
    ) -> None:
        wi = _build(rule_config)
        checked_any = False
        for day in wi.daily_intelligence:
            for factor in day.risk_assessment.risk_factors:
                checked_any = True
                assert factor.rule
                assert factor.rule in KNOWN_RULE_IDS
        assert checked_any, "fixture produced no risk factors to check"


class TestNoAiNarration:
    def test_narrative_is_always_none(self, rule_config: RuleConfig) -> None:
        assert _build(rule_config).narrative is None


class TestGoldenFile:
    def test_output_matches_the_golden_snapshot(self, rule_config: RuleConfig) -> None:
        actual = _to_json_safe(_build(rule_config))
        expected = json.loads(
            (_GOLDEN_DIR / "weather_intelligence_goa_2026_08.json").read_text(encoding="utf-8")
        )
        assert actual == expected


class TestEndToEndScenarios:
    def test_all_clear_trip(self, rule_config: RuleConfig) -> None:
        clear_day_two = NormalizedReading(
            date=date(2026, 8, 2),
            temp_min_c=18.0,
            temp_max_c=24.0,
            precipitation_probability=0.02,
            wind_speed_kph=8.0,
            condition=WeatherCondition.CLEAR,
            completeness=1.0,
            source_class="forecast",
        )
        wi = build_weather_intelligence(
            location=_LOCATION,
            period=_PERIOD,
            readings=[_CLEAR_READING, clear_day_two],
            rule_config=rule_config,
            as_of=_AS_OF,
        )
        assert wi.trip_summary.overall_risk_level == "low"
        assert all(d.travel_advisory == "proceed" for d in wi.daily_intelligence)
        assert wi.trip_summary.overall_packing_list == []
        assert wi.narrative is None

    def test_missing_day_is_absent_not_fabricated(self, rule_config: RuleConfig) -> None:
        # Only one reading for a two-day requested period.
        wi = build_weather_intelligence(
            location=_LOCATION,
            period=_PERIOD,
            readings=[_CLEAR_READING],
            rule_config=rule_config,
            as_of=_AS_OF,
        )
        assert len(wi.daily_intelligence) == 1
        assert wi.period.start_date == date(2026, 8, 1)  # requested period is preserved
        assert wi.period.end_date == date(2026, 8, 2)
