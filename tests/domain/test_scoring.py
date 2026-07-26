"""Tests for `domain.engines.insight.scoring`: base scores, config-driven
adjustments, high-severity doubling, and 0-100 clamping."""

from app.domain.engines.insight.rules import TriggeredRule
from app.domain.engines.insight.scoring import score_activities
from app.domain.rules.config import RuleConfig


def _scores(config: RuleConfig, triggered: list[TriggeredRule]) -> dict[str, int]:
    return {a.activity: a.score for a in score_activities(triggered, config)}


class TestBaseScores:
    def test_no_triggered_rules_yields_base_scores(self, rule_config: RuleConfig) -> None:
        scores = _scores(rule_config, [])
        assert scores == {"outdoor_sightseeing": 80, "beach": 70, "indoor_museum": 60}

    def test_every_configured_activity_category_is_scored(self, rule_config: RuleConfig) -> None:
        scores = _scores(rule_config, [])
        assert set(scores) == {"outdoor_sightseeing", "beach", "indoor_museum"}


class TestPenaltiesAndBonuses:
    def test_moderate_rain_applies_configured_penalty_once(self, rule_config: RuleConfig) -> None:
        triggered = [TriggeredRule("precip_prob_gt_0_6", "rain", "moderate", "rain")]
        scores = _scores(rule_config, triggered)
        assert scores["outdoor_sightseeing"] == 80 - 30
        assert scores["beach"] == 70 - 40
        assert scores["indoor_museum"] == 60 + 20  # indoor_museum has a rain *bonus*

    def test_high_severity_doubles_the_adjustment(self, rule_config: RuleConfig) -> None:
        triggered = [TriggeredRule("precip_prob_gt_high", "rain", "high", "heavy rain")]
        scores = _scores(rule_config, triggered)
        assert scores["outdoor_sightseeing"] == 80 - (30 * 2)
        assert scores["indoor_museum"] == 60 + (20 * 2)

    def test_beach_gets_a_heat_bonus(self, rule_config: RuleConfig) -> None:
        triggered = [TriggeredRule("temp_max_gt_moderate", "heat", "moderate", "warm")]
        scores = _scores(rule_config, triggered)
        assert scores["beach"] == 70 + 10

    def test_unconfigured_factor_type_defaults_to_zero_adjustment(
        self, rule_config: RuleConfig
    ) -> None:
        # `beach` has no configured heat *penalty* entry, only a bonus -- a
        # cold trigger it also has no entry for must be a no-op, not an error.
        triggered = [TriggeredRule("temp_min_lt_moderate", "cold", "moderate", "chilly")]
        scores = _scores(rule_config, triggered)
        assert scores["beach"] == 70 - 30  # beach *does* penalize cold
        assert scores["indoor_museum"] == 60  # indoor_museum has no cold entry at all


class TestClamping:
    def test_score_never_drops_below_zero(self, rule_config: RuleConfig) -> None:
        triggered = [
            TriggeredRule("precip_prob_gt_high", "rain", "high", "rain"),
            TriggeredRule("condition_is_thunderstorm", "storm", "high", "storm"),
            TriggeredRule("wind_speed_gt_high", "wind", "high", "wind"),
            TriggeredRule("temp_max_gt_high", "heat", "high", "hot"),
        ]
        scores = _scores(rule_config, triggered)
        assert all(score >= 0 for score in scores.values())

    def test_score_never_exceeds_one_hundred(self, rule_config: RuleConfig) -> None:
        triggered = [
            TriggeredRule("precip_prob_gt_high", "rain", "high", "rain"),
            TriggeredRule("temp_max_gt_high", "heat", "high", "hot"),
        ]
        scores = _scores(rule_config, triggered)
        assert scores["indoor_museum"] == 100  # 60 + 20*2 + 5*2 = 110 -> clamped
        assert all(score <= 100 for score in scores.values())


class TestDeterminism:
    def test_same_inputs_always_produce_the_same_scores(self, rule_config: RuleConfig) -> None:
        triggered = [TriggeredRule("precip_prob_gt_0_6", "rain", "moderate", "rain")]
        first = _scores(rule_config, triggered)
        for _ in range(50):
            assert _scores(rule_config, triggered) == first
