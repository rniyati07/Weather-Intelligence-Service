"""Tests for `domain.rules.config.parse_rule_config`: a pure function over
already-loaded data — no file I/O, so these belong in `tests/domain`."""

import pytest

from app.domain.rules.config import RuleConfigError, parse_rule_config
from tests.domain.conftest import _RULE_CONFIG_DATA


def _valid_data() -> dict:
    import copy

    return copy.deepcopy(_RULE_CONFIG_DATA)


class TestValidConfig:
    def test_parses_successfully(self) -> None:
        config = parse_rule_config(_valid_data())
        assert config.version == "test-2026.07"
        assert config.insight_thresholds.heat.high_temp_max_c == 35.0
        assert set(config.activity_scoring) == {
            "outdoor_sightseeing",
            "beach",
            "indoor_museum",
        }

    def test_confidence_weights_are_preserved(self) -> None:
        config = parse_rule_config(_valid_data())
        weights = config.confidence_weights
        assert weights.horizon_weight == 0.4
        assert weights.agreement_weight == 0.2
        assert weights.completeness_weight == 0.4


class TestMissingFields:
    def test_missing_version_raises(self) -> None:
        data = _valid_data()
        del data["version"]
        with pytest.raises(RuleConfigError, match="version"):
            parse_rule_config(data)

    def test_missing_insight_thresholds_raises(self) -> None:
        data = _valid_data()
        del data["insight_thresholds"]
        with pytest.raises(RuleConfigError):
            parse_rule_config(data)

    def test_missing_heat_threshold_field_raises(self) -> None:
        data = _valid_data()
        del data["insight_thresholds"]["heat"]["high_temp_max_c"]
        with pytest.raises(RuleConfigError, match="high_temp_max_c"):
            parse_rule_config(data)


class TestActivityScoringValidation:
    def test_missing_activity_category_raises(self) -> None:
        data = _valid_data()
        del data["activity_scoring"]["beach"]
        with pytest.raises(RuleConfigError, match="beach"):
            parse_rule_config(data)

    def test_out_of_range_base_score_raises(self) -> None:
        data = _valid_data()
        data["activity_scoring"]["beach"]["base_score"] = 150
        with pytest.raises(RuleConfigError, match="base_score"):
            parse_rule_config(data)

    def test_unknown_extra_activity_category_is_ignored(self) -> None:
        data = _valid_data()
        data["activity_scoring"]["stargazing"] = {"base_score": 50}
        config = parse_rule_config(data)
        assert "stargazing" not in config.activity_scoring


class TestPackingRulesValidation:
    def test_unknown_risk_factor_type_raises(self) -> None:
        data = _valid_data()
        data["packing_rules"]["hail"] = ["umbrella"]
        with pytest.raises(RuleConfigError, match="hail"):
            parse_rule_config(data)


class TestConfidenceWeightsValidation:
    def test_weights_not_summing_to_one_raises(self) -> None:
        data = _valid_data()
        data["confidence"]["horizon_weight"] = 0.9
        with pytest.raises(RuleConfigError, match="sum to 1.0"):
            parse_rule_config(data)

    def test_weights_summing_to_one_within_float_tolerance_is_accepted(self) -> None:
        data = _valid_data()
        data["confidence"]["horizon_weight"] = 0.4 + 1e-9
        parse_rule_config(data)  # must not raise
