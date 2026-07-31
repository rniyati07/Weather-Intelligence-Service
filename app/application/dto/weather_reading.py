"""Serialisation of `NormalizedReading` to/from the persisted JSONB payload.

Internal DTO mapping (guide §3: `application/dto` holds internal in/out DTOs,
not HTTP schemas). Kept out of the domain so entities stay persistence-free,
and out of the repository so it stores whatever dict it is handed.
"""

from datetime import date
from typing import Any

from app.domain.entities.weather import NormalizedReading, SourceClass, WeatherCondition


def reading_to_payload(reading: NormalizedReading) -> dict[str, Any]:
    """Flatten a reading into the JSON-safe dict stored in `normalized_payload`."""
    return {
        "date": reading.date.isoformat(),
        "temp_min_c": reading.temp_min_c,
        "temp_max_c": reading.temp_max_c,
        "precipitation_probability": reading.precipitation_probability,
        "wind_speed_kph": reading.wind_speed_kph,
        "condition": reading.condition.value,
        "completeness": reading.completeness,
        "source_class": reading.source_class,
        "precipitation_mm": reading.precipitation_mm,
        "humidity": reading.humidity,
    }


def reading_from_payload(payload: dict[str, Any]) -> NormalizedReading:
    """Rebuild a reading from a stored payload.

    An unrecognised persisted condition falls back to `CLOUDY` rather than
    raising, mirroring the forward-compatible enum handling normalization
    already applies (API Spec §12): a rule-vocabulary change must never make
    previously stored rows unreadable.
    """
    try:
        condition = WeatherCondition(payload["condition"])
    except ValueError:
        condition = WeatherCondition.CLOUDY

    source_class: SourceClass = (
        "historical" if payload.get("source_class") == "historical" else "forecast"
    )

    return NormalizedReading(
        date=date.fromisoformat(payload["date"]),
        temp_min_c=float(payload["temp_min_c"]),
        temp_max_c=float(payload["temp_max_c"]),
        precipitation_probability=float(payload["precipitation_probability"]),
        wind_speed_kph=float(payload["wind_speed_kph"]),
        condition=condition,
        completeness=float(payload.get("completeness", 0.0)),
        source_class=source_class,
        precipitation_mm=(
            float(payload["precipitation_mm"])
            if payload.get("precipitation_mm") is not None
            else None
        ),
        humidity=(
            float(payload["humidity"]) if payload.get("humidity") is not None else None
        ),
    )
