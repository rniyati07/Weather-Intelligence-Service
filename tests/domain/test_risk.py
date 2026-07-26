"""Tests for `domain.engines.insight.risk`: max-severity aggregation and
the fixed `RiskLevel` -> `TravelAdvisory` mapping (API Spec §10)."""

import pytest

from app.domain.engines.insight.risk import assess, travel_advisory
from app.domain.engines.insight.rules import TriggeredRule


class TestAssess:
    def test_no_triggered_rules_is_low_risk_with_no_factors(self) -> None:
        result = assess([])
        assert result.overall_risk_level == "low"
        assert result.risk_factors == []

    def test_single_moderate_rule_is_moderate_risk(self) -> None:
        rule = TriggeredRule("precip_prob_gt_0_6", "rain", "moderate", "70% chance of rain.")
        result = assess([rule])
        assert result.overall_risk_level == "moderate"
        assert len(result.risk_factors) == 1
        assert result.risk_factors[0].rule == "precip_prob_gt_0_6"
        assert result.risk_factors[0].type == "rain"
        assert result.risk_factors[0].severity == "moderate"

    def test_mixed_severities_take_the_maximum(self) -> None:
        rules = [
            TriggeredRule("temp_max_gt_moderate", "heat", "moderate", "warm"),
            TriggeredRule("wind_speed_gt_high", "wind", "high", "very windy"),
        ]
        result = assess(rules)
        assert result.overall_risk_level == "high"
        assert len(result.risk_factors) == 2

    def test_every_risk_factor_carries_its_originating_rule_id(self) -> None:
        rules = [
            TriggeredRule("temp_max_gt_high", "heat", "high", "hot"),
            TriggeredRule("wind_speed_gt_moderate", "wind", "moderate", "breezy"),
        ]
        result = assess(rules)
        assert all(factor.rule for factor in result.risk_factors)
        assert {f.rule for f in result.risk_factors} == {
            "temp_max_gt_high",
            "wind_speed_gt_moderate",
        }


class TestTravelAdvisory:
    @pytest.mark.parametrize(
        "risk_level,expected",
        [("low", "proceed"), ("moderate", "caution"), ("high", "avoid")],
    )
    def test_fixed_mapping_matches_api_spec_section_10(
        self, risk_level: str, expected: str
    ) -> None:
        assert travel_advisory(risk_level) == expected  # type: ignore[arg-type]
