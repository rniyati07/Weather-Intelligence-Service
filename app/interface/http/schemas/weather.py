"""Raw (normalized) weather schemas — API Spec §9.9 and the §8.4 payload.

Deliberately omits `completeness` and `source_class`: those are *internal*
normalization fields (they feed `travelConfidence`), and §9.9 does not
publish them. No provider is identified anywhere here.
"""

from datetime import date

from app.domain.entities.weather import NormalizedReading
from app.domain.entities.weather_intelligence import Period, ResolvedLocation
from app.interface.http.schemas.common import CamelModel, LocationSchema, PeriodSchema
from app.interface.http.schemas.intelligence import location_from_domain, period_from_domain


class RawWeatherReadingSchema(CamelModel):
    """API Spec §9.9."""

    date: date
    temp_min_c: float
    temp_max_c: float
    precipitation_probability: float
    precipitation_mm: float | None = None
    wind_speed_kph: float
    humidity: float | None = None
    condition: str

    @classmethod
    def from_domain(cls, reading: NormalizedReading) -> "RawWeatherReadingSchema":
        return cls(
            date=reading.date,
            temp_min_c=reading.temp_min_c,
            temp_max_c=reading.temp_max_c,
            precipitation_probability=reading.precipitation_probability,
            precipitation_mm=reading.precipitation_mm,
            wind_speed_kph=reading.wind_speed_kph,
            humidity=reading.humidity,
            condition=reading.condition.value,
        )


class RawWeatherViewSchema(CamelModel):
    """Payload of `GET .../weather/raw` (API Spec §8.4)."""

    location: LocationSchema
    period: PeriodSchema
    readings: list[RawWeatherReadingSchema]

    @classmethod
    def from_domain(
        cls, location: ResolvedLocation, period: Period, readings: list[NormalizedReading]
    ) -> "RawWeatherViewSchema":
        return cls(
            location=location_from_domain(location),
            period=period_from_domain(period),
            readings=[RawWeatherReadingSchema.from_domain(r) for r in readings],
        )
