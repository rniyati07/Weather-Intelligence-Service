"""Offline persistence tests — no Docker/live DB required.

Two things are verified without a connection: the ORM models compile to
valid PostgreSQL DDL and have the exact columns/indexes/constraints from the
Implementation Guide's Phase 3 schema, and the repository's ORM-row-to-domain
mapping functions produce the expected domain records. Round-tripping actual
SQL against a live database is covered separately in
`tests/integration/test_repositories.py` (Testcontainers-gated).
"""

from datetime import UTC, date, datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.schema import CreateTable

from app.infrastructure.persistence.models import (
    Base,
    LocationModel,
    ProviderModel,
    WeatherIntelligenceDailyModel,
    WeatherReadingRawModel,
)
from app.infrastructure.persistence.repositories import (
    _intelligence_to_domain,
    _location_to_domain,
    _reading_to_domain,
)


def _compiles_for_postgres(table: object) -> str:
    return str(CreateTable(table).compile(dialect=postgresql.dialect()))  # type: ignore[arg-type]


class TestLocationsTable:
    def test_ddl_compiles(self) -> None:
        assert "CREATE TABLE locations" in _compiles_for_postgres(LocationModel.__table__)

    def test_columns(self) -> None:
        columns = LocationModel.__table__.columns
        assert {"id", "name", "latitude", "longitude", "normalized_key"} <= set(columns.keys())

    def test_normalized_key_is_unique(self) -> None:
        unique_columns = {
            col.name
            for constraint in LocationModel.__table__.constraints
            if type(constraint).__name__ == "UniqueConstraint"
            for col in constraint.columns
        }
        assert "normalized_key" in unique_columns


class TestWeatherReadingsRawTable:
    def test_ddl_compiles(self) -> None:
        assert "CREATE TABLE weather_readings_raw" in _compiles_for_postgres(
            WeatherReadingRawModel.__table__
        )

    def test_columns(self) -> None:
        columns = WeatherReadingRawModel.__table__.columns
        expected = {
            "id",
            "location_id",
            "provider",
            "fetched_at",
            "valid_date",
            "raw_payload",
            "normalized_payload",
        }
        assert expected <= set(columns.keys())

    def test_payload_columns_are_jsonb(self) -> None:
        columns = WeatherReadingRawModel.__table__.columns
        assert isinstance(columns["raw_payload"].type, JSONB)
        assert isinstance(columns["normalized_payload"].type, JSONB)

    def test_location_valid_date_index_present(self) -> None:
        index_column_sets = [
            tuple(col.name for col in index.columns)
            for index in WeatherReadingRawModel.__table__.indexes
        ]
        assert ("location_id", "valid_date") in index_column_sets


class TestWeatherIntelligenceDailyTable:
    def test_ddl_compiles(self) -> None:
        assert "CREATE TABLE weather_intelligence_daily" in _compiles_for_postgres(
            WeatherIntelligenceDailyModel.__table__
        )

    def test_columns(self) -> None:
        columns = WeatherIntelligenceDailyModel.__table__.columns
        expected = {
            "id",
            "location_id",
            "date",
            "risk_level",
            "risk_factors",
            "activity_scores",
            "packing",
            "travel_advisory",
            "rule_config_version",
            "generated_at",
        }
        assert expected <= set(columns.keys())

    def test_semi_structured_columns_are_jsonb(self) -> None:
        columns = WeatherIntelligenceDailyModel.__table__.columns
        assert isinstance(columns["risk_factors"].type, JSONB)
        assert isinstance(columns["activity_scores"].type, JSONB)
        assert isinstance(columns["packing"].type, JSONB)

    def test_location_date_version_index_present(self) -> None:
        index_column_sets = [
            tuple(col.name for col in index.columns)
            for index in WeatherIntelligenceDailyModel.__table__.indexes
        ]
        assert ("location_id", "date", "rule_config_version") in index_column_sets

    def test_risk_level_and_travel_advisory_are_constrained(self) -> None:
        ddl = _compiles_for_postgres(WeatherIntelligenceDailyModel.__table__)
        assert "risk_level IN ('low', 'moderate', 'high')" in ddl
        assert "travel_advisory IN ('proceed', 'caution', 'avoid')" in ddl


class TestProvidersTable:
    def test_ddl_compiles(self) -> None:
        assert "CREATE TABLE providers" in _compiles_for_postgres(ProviderModel.__table__)

    def test_columns(self) -> None:
        columns = ProviderModel.__table__.columns
        expected = {"name", "data_class", "priority_order", "is_active", "last_health_check"}
        assert expected <= set(columns.keys())

    def test_data_class_is_constrained(self) -> None:
        ddl = _compiles_for_postgres(ProviderModel.__table__)
        assert "data_class IN ('forecast', 'historical')" in ddl


def test_all_models_share_one_metadata() -> None:
    assert LocationModel.metadata is Base.metadata
    assert WeatherReadingRawModel.metadata is Base.metadata
    assert WeatherIntelligenceDailyModel.metadata is Base.metadata
    assert ProviderModel.metadata is Base.metadata


class TestOrmToDomainMapping:
    def test_location_mapping(self) -> None:
        row = LocationModel(
            id=1, name="Goa", latitude=15.2993, longitude=74.1240, normalized_key="15.2993,74.1240"
        )
        location = _location_to_domain(row)
        assert location.id == 1
        assert location.name == "Goa"
        assert location.normalized_key == "15.2993,74.1240"

    def test_reading_mapping(self) -> None:
        row = WeatherReadingRawModel(
            id=7,
            location_id=1,
            provider="open_meteo",
            fetched_at=datetime(2026, 8, 1, 6, 0, tzinfo=UTC),
            valid_date=date(2026, 8, 1),
            raw_payload={"raw": True},
            normalized_payload={"temp_max_c": 30.0},
        )
        reading = _reading_to_domain(row)
        assert reading.id == 7
        assert reading.provider == "open_meteo"
        assert reading.raw_payload == {"raw": True}
        assert reading.normalized_payload == {"temp_max_c": 30.0}

    def test_intelligence_mapping(self) -> None:
        row = WeatherIntelligenceDailyModel(
            id=3,
            location_id=1,
            date=date(2026, 8, 1),
            risk_level="high",
            risk_factors=[{"rule": "precip_prob_gt_0_6"}],
            activity_scores={"beach": 20},
            packing=["waterproof jacket"],
            travel_advisory="avoid",
            rule_config_version="2026.07",
            generated_at=datetime(2026, 8, 1, 6, 0, tzinfo=UTC),
        )
        record = _intelligence_to_domain(row)
        assert record.risk_level == "high"
        assert record.travel_advisory == "avoid"
        assert record.risk_factors == [{"rule": "precip_prob_gt_0_6"}]
        assert record.rule_config_version == "2026.07"
