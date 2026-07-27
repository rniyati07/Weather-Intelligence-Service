"""Tests for `fallback.build_fallback_narrative`: deterministic, template-only,
composed solely from fields already on `WeatherIntelligence`."""

from datetime import date

from app.domain.entities.weather import WeatherCondition
from app.domain.entities.weather_intelligence import (
    DailyIntelligence,
    DailySummary,
    Period,
    ResolvedLocation,
    RiskAssessment,
    TripSummary,
    WeatherIntelligence,
)
from app.infrastructure.ai.fallback import build_fallback_narrative


def _intelligence(
    *, best_days: list[date], worst_days: list[date], packing: list[str], risk: str
) -> WeatherIntelligence:
    day = DailyIntelligence(
        date=date(2026, 8, 1),
        summary=DailySummary(20.0, 30.0, 0.2, 10.0, WeatherCondition.CLEAR),
        risk_assessment=RiskAssessment(overall_risk_level=risk, risk_factors=[]),  # type: ignore[arg-type]
        activity_suitability=[],
        packing_recommendations=[],
        travel_advisory="proceed",  # type: ignore[arg-type]
    )
    return WeatherIntelligence(
        location=ResolvedLocation(id="15.25,74.125", latitude=15.25, longitude=74.125, name="Goa"),
        period=Period(start_date=date(2026, 8, 1), end_date=date(2026, 8, 1)),
        daily_intelligence=[day],
        trip_summary=TripSummary(
            best_days=best_days,
            worst_days=worst_days,
            overall_packing_list=packing,
            overall_risk_level=risk,  # type: ignore[arg-type]
            trip_suitability_score=70,
            travel_confidence=0.8,
        ),
        rule_config_version="2026.07",
    )


class TestFallbackNarrative:
    def test_marks_itself_as_not_llm_generated(self) -> None:
        narrative = build_fallback_narrative(
            _intelligence(best_days=[date(2026, 8, 1)], worst_days=[], packing=[], risk="low")
        )
        assert narrative.generated_by_llm is False
        assert narrative.fallback_used is True
        assert narrative.model_used is None

    def test_mentions_overall_risk_level(self) -> None:
        narrative = build_fallback_narrative(
            _intelligence(best_days=[date(2026, 8, 1)], worst_days=[], packing=[], risk="high")
        )
        assert "high" in narrative.summary_text

    def test_mentions_best_and_worst_days(self) -> None:
        narrative = build_fallback_narrative(
            _intelligence(
                best_days=[date(2026, 8, 2)],
                worst_days=[date(2026, 8, 1)],
                packing=[],
                risk="moderate",
            )
        )
        assert "2026-08-02" in narrative.summary_text
        assert "2026-08-01" in narrative.summary_text

    def test_mentions_top_packing_items_only(self) -> None:
        narrative = build_fallback_narrative(
            _intelligence(
                best_days=[date(2026, 8, 1)],
                worst_days=[],
                packing=["itemone", "itemtwo", "itemthree", "itemfour", "itemfive"],
                risk="low",
            )
        )
        assert "itemone" in narrative.summary_text
        assert "itemtwo" in narrative.summary_text
        assert "itemthree" in narrative.summary_text
        assert "itemfour" not in narrative.summary_text  # only the top 3 are mentioned

    def test_handles_no_packing_items_gracefully(self) -> None:
        narrative = build_fallback_narrative(
            _intelligence(best_days=[date(2026, 8, 1)], worst_days=[], packing=[], risk="low")
        )
        assert narrative.summary_text  # still non-empty

    def test_is_deterministic(self) -> None:
        intelligence = _intelligence(
            best_days=[date(2026, 8, 1)], worst_days=[date(2026, 8, 2)], packing=["x"], risk="low"
        )
        first = build_fallback_narrative(intelligence)
        for _ in range(20):
            assert build_fallback_narrative(intelligence) == first
