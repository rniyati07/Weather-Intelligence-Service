"""Tests for `domain.engines.recommendation.best_worst.rank_days`.

Ranking is (risk ascending, mean suitability descending, date ascending) --
the date tie-breaker means the result never depends on input order.
"""

from datetime import date

from app.domain.engines.recommendation.best_worst import rank_days
from app.domain.entities.weather import WeatherCondition
from app.domain.entities.weather_intelligence import (
    ActivitySuitability,
    DailyIntelligence,
    DailySummary,
    RiskAssessment,
)


def _day(day: date, risk_level: str, scores: list[int]) -> DailyIntelligence:
    return DailyIntelligence(
        date=day,
        summary=DailySummary(
            temp_min_c=20.0,
            temp_max_c=25.0,
            precipitation_probability=0.1,
            wind_speed_kph=10.0,
            condition=WeatherCondition.CLEAR,
        ),
        risk_assessment=RiskAssessment(overall_risk_level=risk_level, risk_factors=[]),  # type: ignore[arg-type]
        activity_suitability=[
            ActivitySuitability(activity="outdoor_sightseeing", score=scores[0]),  # type: ignore[arg-type]
        ],
        packing_recommendations=[],
        travel_advisory="proceed",  # type: ignore[arg-type]
    )


class TestEmptyInput:
    def test_empty_list_yields_empty_best_and_worst(self) -> None:
        assert rank_days([]) == ([], [])


class TestRiskIsPrimary:
    def test_lower_risk_day_wins_even_with_a_lower_suitability_score(self) -> None:
        low_risk_low_score = _day(date(2026, 8, 1), "low", [40])
        high_risk_high_score = _day(date(2026, 8, 2), "high", [90])

        best, worst = rank_days([low_risk_low_score, high_risk_high_score])

        assert best == [date(2026, 8, 1)]
        assert worst == [date(2026, 8, 2)]


class TestSuitabilityIsSecondary:
    def test_among_equal_risk_higher_suitability_wins(self) -> None:
        lower_score = _day(date(2026, 8, 1), "low", [50])
        higher_score = _day(date(2026, 8, 2), "low", [90])

        best, worst = rank_days([lower_score, higher_score])

        assert best == [date(2026, 8, 2)]
        assert worst == [date(2026, 8, 1)]


class TestDeterministicTieBreak:
    def test_identical_risk_and_suitability_break_ties_by_earlier_date(self) -> None:
        day_a = _day(date(2026, 8, 5), "low", [70])
        day_b = _day(date(2026, 8, 1), "low", [70])
        day_c = _day(date(2026, 8, 3), "low", [70])

        best, worst = rank_days([day_a, day_b, day_c])

        # With risk and suitability tied across all three, the single
        # ascending sort key's date component orders them earliest-to-latest
        # -- so the earliest tied date is picked as "best" and the latest as
        # "worst", deterministically, regardless of input order.
        assert best == [date(2026, 8, 1)]
        assert worst == [date(2026, 8, 5)]

    def test_result_does_not_depend_on_input_order(self) -> None:
        days = [_day(date(2026, 8, 1), "low", [70]), _day(date(2026, 8, 2), "high", [70])]
        forward = rank_days(days)
        backward = rank_days(list(reversed(days)))
        assert forward == backward
