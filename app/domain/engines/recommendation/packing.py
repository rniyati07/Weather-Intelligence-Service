"""Packing recommendations: per-day derivation, and trip-level aggregation.

Order is always fixed by `RuleConfig.packing_item_order` (config-driven, not
insertion order), so the list never depends on which rule or which day
contributed an item first. An item absent from that order (shouldn't happen
if config is authored consistently, but never crash) sorts after it,
alphabetically, for a fully deterministic fallback.
"""

from app.domain.engines.insight.rules import TriggeredRule
from app.domain.rules.config import RuleConfig


def _stable_order(items: set[str], config: RuleConfig) -> list[str]:
    order_index = {item: i for i, item in enumerate(config.packing_item_order)}
    return sorted(items, key=lambda item: (order_index.get(item, len(order_index)), item))


def daily_packing_items(triggered: list[TriggeredRule], config: RuleConfig) -> list[str]:
    """One day's packing items: union of items for every triggered risk factor type."""
    items: set[str] = set()
    for rule in triggered:
        items.update(config.packing_rules.get(rule.factor_type, []))
    return _stable_order(items, config)


def aggregate_packing_list(daily_lists: list[list[str]], config: RuleConfig) -> list[str]:
    """Union + deduplicate every day's packing items into the trip's overall list."""
    items: set[str] = set()
    for daily in daily_lists:
        items.update(daily)
    return _stable_order(items, config)
