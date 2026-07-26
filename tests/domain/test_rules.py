"""Table-driven tests for `domain.engines.insight.rules.evaluate`.

Covers clear/storm days and exact threshold boundaries: the predicates are
strictly `>`/`<`, so a reading sitting exactly on a threshold must NOT
trigger, and one epsilon past it must.
"""

from app.domain.engines.insight.rules import evaluate
from app.domain.entities.weather import WeatherCondition
from app.domain.rules.config import RuleConfig
from tests.domain.conftest import make_reading


class TestClearAndStormDays:
    def test_clear_day_triggers_nothing(self, rule_config: RuleConfig) -> None:
        reading = make_reading(
            temp_min_c=20.0,
            temp_max_c=25.0,
            precipitation_probability=0.1,
            wind_speed_kph=10.0,
            condition=WeatherCondition.CLEAR,
        )
        assert evaluate(reading, rule_config) == []

    def test_storm_day_triggers_every_category_at_high_severity(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(
            temp_min_c=2.0,
            temp_max_c=40.0,
            precipitation_probability=0.95,
            wind_speed_kph=60.0,
            condition=WeatherCondition.THUNDERSTORM,
        )
        triggered = evaluate(reading, rule_config)
        factor_types = {t.factor_type for t in triggered}
        assert factor_types == {"heat", "cold", "rain", "wind", "storm"}
        assert all(t.severity == "high" for t in triggered)


class TestHeatBoundaries:
    def test_exactly_at_moderate_threshold_does_not_trigger(self, rule_config: RuleConfig) -> None:
        reading = make_reading(temp_max_c=30.0)
        assert evaluate(reading, rule_config) == []

    def test_just_above_moderate_threshold_triggers_moderate(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(temp_max_c=30.01)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "temp_max_gt_moderate"
        assert triggered[0].factor_type == "heat"
        assert triggered[0].severity == "moderate"

    def test_exactly_at_high_threshold_triggers_only_moderate(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(temp_max_c=35.0)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].severity == "moderate"

    def test_just_above_high_threshold_triggers_high_only(self, rule_config: RuleConfig) -> None:
        reading = make_reading(temp_max_c=35.01)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "temp_max_gt_high"
        assert triggered[0].severity == "high"


class TestColdBoundaries:
    def test_exactly_at_moderate_threshold_does_not_trigger(self, rule_config: RuleConfig) -> None:
        reading = make_reading(temp_min_c=10.0, temp_max_c=15.0)
        assert evaluate(reading, rule_config) == []

    def test_just_below_moderate_threshold_triggers_moderate(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(temp_min_c=9.99, temp_max_c=15.0)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "temp_min_lt_moderate"
        assert triggered[0].factor_type == "cold"

    def test_just_below_high_threshold_triggers_high_only(self, rule_config: RuleConfig) -> None:
        reading = make_reading(temp_min_c=4.99, temp_max_c=15.0)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].severity == "high"


class TestRainBoundaries:
    def test_exactly_at_moderate_threshold_does_not_trigger(self, rule_config: RuleConfig) -> None:
        reading = make_reading(precipitation_probability=0.6)
        assert evaluate(reading, rule_config) == []

    def test_just_above_moderate_threshold_triggers_the_guides_example_rule_id(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(precipitation_probability=0.61)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        # The guide's own example rule id (§Phase 7 step 2) -- verbatim.
        assert triggered[0].rule_id == "precip_prob_gt_0_6"
        assert triggered[0].factor_type == "rain"
        assert triggered[0].severity == "moderate"

    def test_just_above_high_threshold_triggers_high_only(self, rule_config: RuleConfig) -> None:
        reading = make_reading(precipitation_probability=0.81)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].severity == "high"


class TestWindBoundaries:
    def test_exactly_at_moderate_threshold_does_not_trigger(self, rule_config: RuleConfig) -> None:
        reading = make_reading(wind_speed_kph=25.0)
        assert evaluate(reading, rule_config) == []

    def test_just_above_moderate_threshold_triggers_moderate(
        self, rule_config: RuleConfig
    ) -> None:
        reading = make_reading(wind_speed_kph=25.01)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "wind_speed_gt_moderate"
        assert triggered[0].factor_type == "wind"

    def test_just_above_high_threshold_triggers_high_only(self, rule_config: RuleConfig) -> None:
        reading = make_reading(wind_speed_kph=40.01)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].severity == "high"


class TestStormCondition:
    def test_thunderstorm_triggers_high_storm(self, rule_config: RuleConfig) -> None:
        reading = make_reading(condition=WeatherCondition.THUNDERSTORM)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "condition_is_thunderstorm"
        assert triggered[0].factor_type == "storm"
        assert triggered[0].severity == "high"

    def test_heavy_rain_triggers_moderate_storm(self, rule_config: RuleConfig) -> None:
        reading = make_reading(condition=WeatherCondition.HEAVY_RAIN)
        triggered = evaluate(reading, rule_config)
        assert len(triggered) == 1
        assert triggered[0].rule_id == "condition_is_heavy_rain"
        assert triggered[0].factor_type == "storm"
        assert triggered[0].severity == "moderate"

    def test_plain_rain_condition_does_not_trigger_storm(self, rule_config: RuleConfig) -> None:
        reading = make_reading(condition=WeatherCondition.RAIN)
        assert evaluate(reading, rule_config) == []


class TestIndependentCategories:
    def test_multiple_categories_trigger_simultaneously(self, rule_config: RuleConfig) -> None:
        reading = make_reading(
            temp_max_c=36.0,  # heat: high
            wind_speed_kph=26.0,  # wind: moderate
            precipitation_probability=0.1,
            temp_min_c=20.0,
        )
        triggered = evaluate(reading, rule_config)
        by_type = {t.factor_type: t.severity for t in triggered}
        assert by_type == {"heat": "high", "wind": "moderate"}
