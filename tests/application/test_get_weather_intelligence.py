"""`GetWeatherIntelligence` — the `get_fresh_intelligence` write-avoidance guard.

`FakeRepository` in `tests/api/conftest.py` always returns `[]` from
`get_fresh_intelligence`, which is why the whole existing 306-test suite
exercises only the "nothing fresh yet, persist everything" branch and never
caught this method sitting unused. These tests exercise the branch that
`FakeRepository` never does: rows that already exist and are fresh.
"""

from datetime import UTC, date, datetime
from typing import Any

from app.application.use_cases.get_weather_intelligence import GetWeatherIntelligence
from app.application.use_cases.load_readings import (
    CACHE_MISS,
    LoadedReadings,
    WeatherReadingsLoader,
)
from app.domain.entities.persistence import DailyIntelligenceRecord, Location, RawWeatherReading
from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.ports.repository import WeatherRepository
from app.domain.rules.config import parse_rule_config

_RULE_CONFIG_DATA: dict[str, Any] = {
    "version": "test-2026.07",
    "insight_thresholds": {
        "heat": {"moderate_temp_max_c": 30.0, "high_temp_max_c": 35.0},
        "cold": {"moderate_temp_min_c": 10.0, "high_temp_min_c": 5.0},
        "rain": {"moderate_precip_probability": 0.6, "high_precip_probability": 0.8},
        "wind": {"moderate_wind_speed_kph": 25.0, "high_wind_speed_kph": 40.0},
    },
    "activity_scoring": {
        "outdoor_sightseeing": {"base_score": 80, "penalties": {}, "bonuses": {}},
        "beach": {"base_score": 70, "penalties": {}, "bonuses": {}},
        "indoor_museum": {"base_score": 60, "penalties": {}, "bonuses": {}},
    },
    "packing_rules": {},
    "packing_item_order": [],
    "confidence": {
        "horizon_weight": 0.4,
        "agreement_weight": 0.2,
        "completeness_weight": 0.4,
        "max_horizon_days": 16,
        "single_provider_neutral_factor": 0.8,
    },
}


def _reading(day: date) -> NormalizedReading:
    return NormalizedReading(
        date=day,
        temp_min_c=20.0,
        temp_max_c=27.0,
        precipitation_probability=0.1,
        wind_speed_kph=10.0,
        condition=WeatherCondition.CLEAR,
        completeness=1.0,
        source_class="forecast",
    )


class SpyRepository(WeatherRepository):
    """Records every `save_intelligence` call and scripts `get_fresh_intelligence`."""

    def __init__(self, *, fresh_dates: set[date] | None = None) -> None:
        self.saved_dates: list[date] = []
        self._fresh_dates = fresh_dates or set()

    async def get_or_create_location(
        self, *, name, latitude, longitude, normalized_key
    ) -> Location:
        return Location(
            id=1, name=name, latitude=latitude, longitude=longitude, normalized_key=normalized_key
        )

    async def save_raw_reading(self, reading: RawWeatherReading) -> RawWeatherReading:
        return reading

    async def get_raw_readings(
        self, *, location_id, start_date, end_date
    ) -> list[RawWeatherReading]:
        return []

    async def save_intelligence(self, record: DailyIntelligenceRecord) -> DailyIntelligenceRecord:
        self.saved_dates.append(record.date)
        return record

    async def get_fresh_intelligence(
        self, *, location_id, start_date, end_date, rule_config_version, fresh_since
    ) -> list[DailyIntelligenceRecord]:
        return [
            DailyIntelligenceRecord(
                location_id=location_id,
                date=day,
                risk_level="low",
                risk_factors=[],
                activity_scores={},
                packing=[],
                travel_advisory="proceed",
                rule_config_version=rule_config_version,
                generated_at=datetime.now(UTC),
            )
            for day in self._fresh_dates
            if start_date <= day <= end_date
        ]


class StubLoader(WeatherReadingsLoader):
    """A loader that always reports a cache miss with a fixed set of readings."""

    def __init__(self, readings: list[NormalizedReading]) -> None:
        self._readings = readings

    async def load(self, *, latitude, longitude, start, end, name=None) -> LoadedReadings:
        return LoadedReadings(
            location_id=1, readings=self._readings, cache_status=CACHE_MISS, degraded=False
        )


class TestFreshnessGuard:
    async def test_disabled_by_default_persists_every_day(self) -> None:
        repository = SpyRepository()
        readings = [_reading(date(2026, 8, 1)), _reading(date(2026, 8, 2))]
        use_case = GetWeatherIntelligence(
            loader=StubLoader(readings),
            repository=repository,
            rule_config=parse_rule_config(_RULE_CONFIG_DATA),
        )

        await use_case.execute(
            latitude=15.3, longitude=74.1, start=date(2026, 8, 1), end=date(2026, 8, 2)
        )

        assert sorted(repository.saved_dates) == [date(2026, 8, 1), date(2026, 8, 2)]

    async def test_enabled_but_nothing_fresh_persists_every_day(self) -> None:
        repository = SpyRepository(fresh_dates=set())
        readings = [_reading(date(2026, 8, 1)), _reading(date(2026, 8, 2))]
        use_case = GetWeatherIntelligence(
            loader=StubLoader(readings),
            repository=repository,
            rule_config=parse_rule_config(_RULE_CONFIG_DATA),
            intelligence_ttl_seconds=3600,
        )

        await use_case.execute(
            latitude=15.3, longitude=74.1, start=date(2026, 8, 1), end=date(2026, 8, 2)
        )

        assert sorted(repository.saved_dates) == [date(2026, 8, 1), date(2026, 8, 2)]

    async def test_days_already_fresh_are_not_re_persisted(self) -> None:
        """The actual fix: day 1 already has a fresh row -> skip it; day 2 doesn't -> write it."""
        repository = SpyRepository(fresh_dates={date(2026, 8, 1)})
        readings = [_reading(date(2026, 8, 1)), _reading(date(2026, 8, 2))]
        use_case = GetWeatherIntelligence(
            loader=StubLoader(readings),
            repository=repository,
            rule_config=parse_rule_config(_RULE_CONFIG_DATA),
            intelligence_ttl_seconds=3600,
        )

        await use_case.execute(
            latitude=15.3, longitude=74.1, start=date(2026, 8, 1), end=date(2026, 8, 2)
        )

        assert repository.saved_dates == [date(2026, 8, 2)]

    async def test_all_days_fresh_persists_nothing(self) -> None:
        repository = SpyRepository(fresh_dates={date(2026, 8, 1), date(2026, 8, 2)})
        readings = [_reading(date(2026, 8, 1)), _reading(date(2026, 8, 2))]
        use_case = GetWeatherIntelligence(
            loader=StubLoader(readings),
            repository=repository,
            rule_config=parse_rule_config(_RULE_CONFIG_DATA),
            intelligence_ttl_seconds=3600,
        )

        await use_case.execute(
            latitude=15.3, longitude=74.1, start=date(2026, 8, 1), end=date(2026, 8, 2)
        )

        assert repository.saved_dates == []

    async def test_the_computed_response_is_unaffected_by_the_guard(self) -> None:
        """Skipping a *write* must never skip returning the computed value."""
        repository = SpyRepository(fresh_dates={date(2026, 8, 1), date(2026, 8, 2)})
        readings = [_reading(date(2026, 8, 1)), _reading(date(2026, 8, 2))]
        use_case = GetWeatherIntelligence(
            loader=StubLoader(readings),
            repository=repository,
            rule_config=parse_rule_config(_RULE_CONFIG_DATA),
            intelligence_ttl_seconds=3600,
        )

        result = await use_case.execute(
            latitude=15.3, longitude=74.1, start=date(2026, 8, 1), end=date(2026, 8, 2)
        )

        assert len(result.intelligence.daily_intelligence) == 2
