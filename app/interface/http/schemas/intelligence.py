"""Weather-intelligence response schemas — API Spec §9.1 and §9.4-9.8, field-for-field.

These mirror the domain entities in `domain/entities/weather_intelligence.py`
but are the *external* contract: camelCase, and built with `from_domain`
constructors so a router never hand-assembles a payload.
"""

from datetime import date

from app.domain.entities.weather_intelligence import (
    ActivitySuitability,
    DailyIntelligence,
    DailySummary,
    Narrative,
    Period,
    ResolvedLocation,
    RiskAssessment,
    RiskFactor,
    TripSummary,
    WeatherIntelligence,
)
from app.interface.http.schemas.common import CamelModel, LocationSchema, PeriodSchema


def location_from_domain(location: ResolvedLocation) -> LocationSchema:
    return LocationSchema(
        id=location.id,
        latitude=location.latitude,
        longitude=location.longitude,
        name=location.name,
    )


def period_from_domain(period: Period) -> PeriodSchema:
    return PeriodSchema(start_date=period.start_date, end_date=period.end_date)


class DailySummarySchema(CamelModel):
    """API Spec §9.4.1."""

    temp_min_c: float
    temp_max_c: float
    precipitation_probability: float
    wind_speed_kph: float
    condition: str

    @classmethod
    def from_domain(cls, summary: DailySummary) -> "DailySummarySchema":
        return cls(
            temp_min_c=summary.temp_min_c,
            temp_max_c=summary.temp_max_c,
            precipitation_probability=summary.precipitation_probability,
            wind_speed_kph=summary.wind_speed_kph,
            condition=summary.condition.value,
        )


class RiskFactorSchema(CamelModel):
    """API Spec §9.4.3. `rule` is the explainability anchor (NFR-1)."""

    type: str
    severity: str
    description: str
    rule: str

    @classmethod
    def from_domain(cls, factor: RiskFactor) -> "RiskFactorSchema":
        return cls(
            type=factor.type,
            severity=factor.severity,
            description=factor.description,
            rule=factor.rule,
        )


class RiskAssessmentSchema(CamelModel):
    """API Spec §9.4.2."""

    overall_risk_level: str
    risk_factors: list[RiskFactorSchema]

    @classmethod
    def from_domain(cls, assessment: RiskAssessment) -> "RiskAssessmentSchema":
        return cls(
            overall_risk_level=assessment.overall_risk_level,
            risk_factors=[RiskFactorSchema.from_domain(f) for f in assessment.risk_factors],
        )


class ActivitySuitabilitySchema(CamelModel):
    """API Spec §9.4.4."""

    activity: str
    score: int

    @classmethod
    def from_domain(cls, activity: ActivitySuitability) -> "ActivitySuitabilitySchema":
        return cls(activity=activity.activity, score=activity.score)


class DailyIntelligenceSchema(CamelModel):
    """API Spec §9.4."""

    date: date
    summary: DailySummarySchema
    risk_assessment: RiskAssessmentSchema
    activity_suitability: list[ActivitySuitabilitySchema]
    packing_recommendations: list[str]
    travel_advisory: str

    @classmethod
    def from_domain(cls, day: DailyIntelligence) -> "DailyIntelligenceSchema":
        return cls(
            date=day.date,
            summary=DailySummarySchema.from_domain(day.summary),
            risk_assessment=RiskAssessmentSchema.from_domain(day.risk_assessment),
            activity_suitability=[
                ActivitySuitabilitySchema.from_domain(a) for a in day.activity_suitability
            ],
            packing_recommendations=list(day.packing_recommendations),
            travel_advisory=day.travel_advisory,
        )


class TripSummarySchema(CamelModel):
    """API Spec §9.5."""

    best_days: list[date]
    worst_days: list[date]
    overall_packing_list: list[str]
    overall_risk_level: str
    trip_suitability_score: int
    travel_confidence: float

    @classmethod
    def from_domain(cls, summary: TripSummary) -> "TripSummarySchema":
        return cls(
            best_days=list(summary.best_days),
            worst_days=list(summary.worst_days),
            overall_packing_list=list(summary.overall_packing_list),
            overall_risk_level=summary.overall_risk_level,
            trip_suitability_score=summary.trip_suitability_score,
            travel_confidence=summary.travel_confidence,
        )


class NarrativeSchema(CamelModel):
    """API Spec §9.6."""

    generated_by_llm: bool
    summary_text: str
    model_used: str | None = None
    fallback_used: bool

    @classmethod
    def from_domain(cls, narrative: Narrative) -> "NarrativeSchema":
        return cls(
            generated_by_llm=narrative.generated_by_llm,
            summary_text=narrative.summary_text,
            model_used=narrative.model_used,
            fallback_used=narrative.fallback_used,
        )


class WeatherIntelligenceSchema(CamelModel):
    """API Spec §9.1 — root payload of `GET .../intelligence`.

    `narrative` is always `null` here; it is produced only by the separate
    `POST .../narrative` endpoint (API Spec §8.1 business rules).
    """

    location: LocationSchema
    period: PeriodSchema
    daily_intelligence: list[DailyIntelligenceSchema]
    trip_summary: TripSummarySchema
    narrative: NarrativeSchema | None = None

    @classmethod
    def from_domain(cls, intelligence: WeatherIntelligence) -> "WeatherIntelligenceSchema":
        return cls(
            location=location_from_domain(intelligence.location),
            period=period_from_domain(intelligence.period),
            daily_intelligence=[
                DailyIntelligenceSchema.from_domain(d) for d in intelligence.daily_intelligence
            ],
            trip_summary=TripSummarySchema.from_domain(intelligence.trip_summary),
            narrative=(
                NarrativeSchema.from_domain(intelligence.narrative)
                if intelligence.narrative is not None
                else None
            ),
        )


class BestDaysViewSchema(CamelModel):
    """API Spec §9.7 — a projection of the same computation as §9.1."""

    location: LocationSchema
    period: PeriodSchema
    best_days: list[date]
    worst_days: list[date]
    overall_risk_level: str

    @classmethod
    def from_domain(cls, intelligence: WeatherIntelligence) -> "BestDaysViewSchema":
        trip = intelligence.trip_summary
        return cls(
            location=location_from_domain(intelligence.location),
            period=period_from_domain(intelligence.period),
            best_days=list(trip.best_days),
            worst_days=list(trip.worst_days),
            overall_risk_level=trip.overall_risk_level,
        )


class PackingViewSchema(CamelModel):
    """API Spec §9.8 — a projection of the same computation as §9.1."""

    location: LocationSchema
    period: PeriodSchema
    overall_packing_list: list[str]

    @classmethod
    def from_domain(cls, intelligence: WeatherIntelligence) -> "PackingViewSchema":
        return cls(
            location=location_from_domain(intelligence.location),
            period=period_from_domain(intelligence.period),
            overall_packing_list=list(intelligence.trip_summary.overall_packing_list),
        )


class NarrativeViewSchema(CamelModel):
    """Payload of `POST .../narrative` (API Spec §8.5)."""

    location: LocationSchema
    period: PeriodSchema
    narrative: NarrativeSchema
