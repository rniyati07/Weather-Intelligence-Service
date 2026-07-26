"""Tests for `domain.engines.recommendation.packing`: per-day derivation and
trip-level aggregation, both deduplicated and in config-driven stable order."""

from app.domain.engines.insight.rules import TriggeredRule
from app.domain.engines.recommendation.packing import aggregate_packing_list, daily_packing_items
from app.domain.rules.config import RuleConfig


class TestDailyPackingItems:
    def test_no_triggered_rules_yields_no_items(self, rule_config: RuleConfig) -> None:
        assert daily_packing_items([], rule_config) == []

    def test_rain_rule_contributes_its_configured_items(self, rule_config: RuleConfig) -> None:
        triggered = [TriggeredRule("precip_prob_gt_0_6", "rain", "moderate", "rain")]
        items = daily_packing_items(triggered, rule_config)
        assert items == ["waterproof jacket", "quick-dry footwear"]

    def test_overlapping_items_across_rules_are_deduplicated(
        self, rule_config: RuleConfig
    ) -> None:
        # Both rain and storm rules contribute "waterproof jacket".
        triggered = [
            TriggeredRule("precip_prob_gt_0_6", "rain", "moderate", "rain"),
            TriggeredRule("condition_is_heavy_rain", "storm", "moderate", "storm"),
        ]
        items = daily_packing_items(triggered, rule_config)
        assert items.count("waterproof jacket") == 1

    def test_items_follow_the_configured_stable_order(self, rule_config: RuleConfig) -> None:
        triggered = [
            TriggeredRule("wind_speed_gt_moderate", "wind", "moderate", "windy"),
            TriggeredRule("temp_max_gt_moderate", "heat", "moderate", "hot"),
        ]
        items = daily_packing_items(triggered, rule_config)
        # windbreaker precedes light cottons/sunscreen in packing_item_order.
        assert items.index("windbreaker") < items.index("sunscreen")


class TestAggregatePackingList:
    def test_empty_days_yields_empty_list(self, rule_config: RuleConfig) -> None:
        assert aggregate_packing_list([], rule_config) == []

    def test_union_across_days_is_deduplicated(self, rule_config: RuleConfig) -> None:
        day_one = ["waterproof jacket", "sunscreen"]
        day_two = ["waterproof jacket", "windbreaker"]
        result = aggregate_packing_list([day_one, day_two], rule_config)
        assert result.count("waterproof jacket") == 1
        assert set(result) == {"waterproof jacket", "sunscreen", "windbreaker"}

    def test_result_follows_the_configured_stable_order_regardless_of_input_order(
        self, rule_config: RuleConfig
    ) -> None:
        forward = aggregate_packing_list([["sunscreen", "windbreaker"]], rule_config)
        backward = aggregate_packing_list([["windbreaker", "sunscreen"]], rule_config)
        assert forward == backward == ["windbreaker", "sunscreen"]
