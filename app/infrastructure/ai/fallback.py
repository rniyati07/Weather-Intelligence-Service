"""Deterministic, templated narration — the guaranteed fallback path.

Composed only from fields already present on `WeatherIntelligence`: best
day, worst day, overall risk, and the top packing items. No LLM, no
randomness, no clock — the same intelligence always yields the same text,
which is what makes this a safe, unconditional fallback rather than a
best-effort one.
"""

from app.domain.entities.weather_intelligence import Narrative, WeatherIntelligence

_TOP_PACKING_ITEMS = 3


def build_fallback_narrative(intelligence: WeatherIntelligence) -> Narrative:
    """Build a `Narrative` template-composed from `intelligence`, never calling AI."""
    trip = intelligence.trip_summary
    best = ", ".join(d.isoformat() for d in trip.best_days) or "no clear best day"
    worst = ", ".join(d.isoformat() for d in trip.worst_days) or "no notably worse day"
    packing_preview = trip.overall_packing_list[:_TOP_PACKING_ITEMS]

    summary_parts = [
        f"Overall trip risk is {trip.overall_risk_level}.",
        f"The best day to travel is {best}, and the worst is {worst}.",
    ]
    if packing_preview:
        summary_parts.append(f"Consider packing: {', '.join(packing_preview)}.")

    return Narrative(
        generated_by_llm=False,
        summary_text=" ".join(summary_parts),
        fallback_used=True,
        model_used=None,
    )
