"""`reading_to_payload`/`reading_from_payload` round-trip.

This DTO whitelists fields explicitly (guide §3), so a field added to
`NormalizedReading` without a matching change here is silently dropped on
persist and silently read back as `None` on every cache-hit thereafter —
exactly the bug this file guards against.
"""

from datetime import date

from app.application.dto.weather_reading import reading_from_payload, reading_to_payload
from app.domain.entities.weather import NormalizedReading, WeatherCondition

_ENRICHED = NormalizedReading(
    date=date(2026, 9, 30),
    temp_min_c=23.0,
    temp_max_c=31.0,
    precipitation_probability=0.51,
    wind_speed_kph=18.0,
    condition=WeatherCondition.RAIN,
    completeness=1.0,
    source_class="forecast",
    humidity=0.86,
    precipitation_mm=4.2,
    feels_like_max_c=38.0,
    feels_like_min_c=25.0,
    uv_index_max=9.0,
    wind_gust_kph=23.0,
    sunrise="2026-09-30T00:53",
    sunset="2026-09-30T12:47",
)


class TestReadingPayloadRoundTrip:
    def test_new_real_fields_survive_a_round_trip(self) -> None:
        payload = reading_to_payload(_ENRICHED)
        restored = reading_from_payload(payload)

        assert restored.feels_like_max_c == 38.0
        assert restored.feels_like_min_c == 25.0
        assert restored.uv_index_max == 9.0
        assert restored.wind_gust_kph == 23.0
        assert restored.sunrise == "2026-09-30T00:53"
        assert restored.sunset == "2026-09-30T12:47"

    def test_missing_new_fields_in_a_stored_payload_degrade_to_none(self) -> None:
        """An older row persisted before these fields existed must still load."""
        payload = reading_to_payload(_ENRICHED)
        for key in (
            "feels_like_max_c",
            "feels_like_min_c",
            "uv_index_max",
            "wind_gust_kph",
            "sunrise",
            "sunset",
        ):
            del payload[key]

        restored = reading_from_payload(payload)

        assert restored.feels_like_max_c is None
        assert restored.feels_like_min_c is None
        assert restored.uv_index_max is None
        assert restored.wind_gust_kph is None
        assert restored.sunrise is None
        assert restored.sunset is None
