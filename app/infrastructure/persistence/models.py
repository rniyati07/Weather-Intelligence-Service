"""SQLAlchemy ORM models for the four persisted tables (TRD §7.1, guide §Phase 3).

Infrastructure-only: repositories translate to and from the plain domain
records in `domain/entities/persistence.py`. No ORM instance crosses the
`WeatherRepository` port boundary.
"""

from datetime import date as date_
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Imported as `date_`, not `date`: `WeatherIntelligenceDailyModel` has a column
# literally named `date`, which would otherwise shadow the type in its own
# `Mapped[date]` annotation during SQLAlchemy's class-level type resolution.


class Base(DeclarativeBase):
    pass


class LocationModel(Base):
    """A canonical place, keyed by a stable, normalized coordinate string."""

    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("normalized_key", name="uq_locations_normalized_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_key: Mapped[str] = mapped_column(String(64), nullable=False)


class WeatherReadingRawModel(Base):
    """One provider's raw + normalized payload for a location on a given date."""

    __tablename__ = "weather_readings_raw"
    __table_args__ = (
        Index("ix_weather_readings_raw_location_valid_date", "location_id", "valid_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_date: Mapped[date_] = mapped_column(nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    normalized_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WeatherIntelligenceDailyModel(Base):
    """Computed per-day intelligence, stamped with the rule config version behind it."""

    __tablename__ = "weather_intelligence_daily"
    __table_args__ = (
        Index(
            "ix_weather_intelligence_daily_location_date_version",
            "location_id",
            "date",
            "rule_config_version",
        ),
        CheckConstraint(
            "risk_level IN ('low', 'moderate', 'high')",
            name="ck_weather_intelligence_daily_risk_level",
        ),
        CheckConstraint(
            "travel_advisory IN ('proceed', 'caution', 'avoid')",
            name="ck_weather_intelligence_daily_travel_advisory",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    date: Mapped[date_] = mapped_column(nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    activity_scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    packing: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    travel_advisory: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_config_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderModel(Base):
    """Provider registry state: priority, activity, and last observed health."""

    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint(
            "data_class IN ('forecast', 'historical')", name="ck_providers_data_class"
        ),
    )

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    data_class: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
