"""Tests for `domain.engines.recommendation.trip_scores`.

`travel_confidence` gets the most scrutiny: TRD §7.5 requires it to be a
deterministic function of exactly three inputs, with longer horizon and
lower completeness each *monotonically* reducing it.
"""

from datetime import date, timedelta

from app.domain.engines.recommendation.trip_scores import (
    overall_risk_level,
    travel_confidence,
    trip_suitability_score,
)
from app.domain.entities.weather import WeatherCondition
from app.domain.entities.weather_intelligence import (
    ActivitySuitability,
    DailyIntelligence,
    DailySummary,
    RiskAssessment,
)
from app.domain.rules.config import RuleConfig


def _day(risk_level: str, scores: list[int], day: date = date(2026, 8, 1)) -> DailyIntelligence:
    return DailyIntelligence(
        date=day,
        summary=DailySummary(20.0, 25.0, 0.1, 10.0, WeatherCondition.CLEAR),
        risk_assessment=RiskAssessment(overall_risk_level=risk_level, risk_factors=[]),  # type: ignore[arg-type]
        activity_suitability=[
            ActivitySuitability(activity="outdoor_sightseeing", score=scores[0]),  # type: ignore[arg-type]
        ],
        packing_recommendations=[],
        travel_advisory="proceed",  # type: ignore[arg-type]
    )


class TestOverallRiskLevel:
    def test_empty_days_is_low(self) -> None:
        assert overall_risk_level([]) == "low"

    def test_worst_case_wins(self) -> None:
        days = [_day("low", [80]), _day("high", [50]), _day("moderate", [60])]
        assert overall_risk_level(days) == "high"

    def test_all_low_is_low(self) -> None:
        days = [_day("low", [80]), _day("low", [90])]
        assert overall_risk_level(days) == "low"


class TestTripSuitabilityScore:
    def test_empty_days_is_zero(self) -> None:
        assert trip_suitability_score([]) == 0

    def test_single_day_matches_its_own_mean(self) -> None:
        assert trip_suitability_score([_day("low", [80])]) == 80

    def test_averages_across_days(self) -> None:
        days = [_day("low", [100]), _day("low", [0])]
        assert trip_suitability_score(days) == 50

    def test_result_is_clamped_to_0_100(self) -> None:
        days = [_day("low", [100]), _day("low", [100])]
        score = trip_suitability_score(days)
        assert 0 <= score <= 100


class TestTravelConfidence:
    def test_result_is_within_0_1(self, rule_config: RuleConfig) -> None:
        confidence = travel_confidence(
            reading_dates=[date(2026, 8, 1)],
            as_of=date(2026, 7, 26),
            mean_completeness=1.0,
            provider_agreement_factor=0.8,
            config=rule_config,
        )
        assert 0.0 <= confidence <= 1.0

    def test_no_reading_dates_yields_zero_horizon_contribution(
        self, rule_config: RuleConfig
    ) -> None:
        confidence = travel_confidence(
            reading_dates=[],
            as_of=date(2026, 7, 26),
            mean_completeness=1.0,
            provider_agreement_factor=0.8,
            config=rule_config,
        )
        expected = (
            rule_config.confidence_weights.agreement_weight * 0.8
            + rule_config.confidence_weights.completeness_weight * 1.0
        )
        assert confidence == expected

    def test_longer_horizon_monotonically_reduces_confidence(
        self, rule_config: RuleConfig
    ) -> None:
        as_of = date(2026, 7, 26)
        confidences = [
            travel_confidence(
                reading_dates=[as_of + timedelta(days=days_out)],
                as_of=as_of,
                mean_completeness=1.0,
                provider_agreement_factor=0.8,
                config=rule_config,
            )
            for days_out in (0, 3, 6, 9, 12, 15)
        ]
        pairs = zip(confidences, confidences[1:], strict=False)
        assert all(earlier >= later for earlier, later in pairs)
        assert confidences[0] > confidences[-1]  # strictly lower somewhere, not just flat

    def test_lower_completeness_monotonically_reduces_confidence(
        self, rule_config: RuleConfig
    ) -> None:
        as_of = date(2026, 7, 26)
        confidences = [
            travel_confidence(
                reading_dates=[as_of],
                as_of=as_of,
                mean_completeness=completeness,
                provider_agreement_factor=0.8,
                config=rule_config,
            )
            for completeness in (1.0, 0.75, 0.5, 0.25, 0.0)
        ]
        pairs = zip(confidences, confidences[1:], strict=False)
        assert all(earlier >= later for earlier, later in pairs)
        assert confidences[0] > confidences[-1]

    def test_lower_agreement_factor_reduces_confidence(self, rule_config: RuleConfig) -> None:
        as_of = date(2026, 7, 26)
        high_agreement = travel_confidence(
            reading_dates=[as_of],
            as_of=as_of,
            mean_completeness=1.0,
            provider_agreement_factor=1.0,
            config=rule_config,
        )
        low_agreement = travel_confidence(
            reading_dates=[as_of],
            as_of=as_of,
            mean_completeness=1.0,
            provider_agreement_factor=0.0,
            config=rule_config,
        )
        assert high_agreement > low_agreement

    def test_is_deterministic(self, rule_config: RuleConfig) -> None:
        kwargs = {
            "reading_dates": [date(2026, 8, 1), date(2026, 8, 2)],
            "as_of": date(2026, 7, 26),
            "mean_completeness": 0.75,
            "provider_agreement_factor": 0.8,
            "config": rule_config,
        }
        first = travel_confidence(**kwargs)  # type: ignore[arg-type]
        for _ in range(50):
            assert travel_confidence(**kwargs) == first  # type: ignore[arg-type]
