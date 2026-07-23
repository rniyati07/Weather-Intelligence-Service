"""SQLAlchemy implementation of the `WeatherRepository` port.

Translates between ORM rows and the plain domain records in
`domain/entities/persistence.py`. No ORM instance is ever returned across
the port boundary — only `select()`, `.scalars()`, and mapping happen here.
"""

from datetime import date, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.persistence import (
    DailyIntelligenceRecord,
    Location,
    RawWeatherReading,
    RiskLevel,
    TravelAdvisory,
)
from app.domain.ports.repository import WeatherRepository
from app.infrastructure.persistence.models import (
    LocationModel,
    WeatherIntelligenceDailyModel,
    WeatherReadingRawModel,
)


def _location_to_domain(row: LocationModel) -> Location:
    return Location(
        id=row.id,
        name=row.name,
        latitude=row.latitude,
        longitude=row.longitude,
        normalized_key=row.normalized_key,
    )


def _reading_to_domain(row: WeatherReadingRawModel) -> RawWeatherReading:
    return RawWeatherReading(
        id=row.id,
        location_id=row.location_id,
        provider=row.provider,
        fetched_at=row.fetched_at,
        valid_date=row.valid_date,
        raw_payload=row.raw_payload,
        normalized_payload=row.normalized_payload,
    )


def _intelligence_to_domain(row: WeatherIntelligenceDailyModel) -> DailyIntelligenceRecord:
    # risk_level/travel_advisory are DB-constrained (CHECK constraints in
    # models.py) to exactly these literals, so the cast is safe.
    return DailyIntelligenceRecord(
        id=row.id,
        location_id=row.location_id,
        date=row.date,
        risk_level=cast(RiskLevel, row.risk_level),
        risk_factors=row.risk_factors,
        activity_scores=row.activity_scores,
        packing=row.packing,
        travel_advisory=cast(TravelAdvisory, row.travel_advisory),
        rule_config_version=row.rule_config_version,
        generated_at=row.generated_at,
    )


class SqlAlchemyWeatherRepository(WeatherRepository):
    """`WeatherRepository` backed by SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_location(
        self, *, name: str, latitude: float, longitude: float, normalized_key: str
    ) -> Location:
        stmt = select(LocationModel).where(LocationModel.normalized_key == normalized_key)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return _location_to_domain(existing)

        row = LocationModel(
            name=name, latitude=latitude, longitude=longitude, normalized_key=normalized_key
        )
        self._session.add(row)
        await self._session.flush()
        return _location_to_domain(row)

    async def save_raw_reading(self, reading: RawWeatherReading) -> RawWeatherReading:
        row = WeatherReadingRawModel(
            location_id=reading.location_id,
            provider=reading.provider,
            fetched_at=reading.fetched_at,
            valid_date=reading.valid_date,
            raw_payload=reading.raw_payload,
            normalized_payload=reading.normalized_payload,
        )
        self._session.add(row)
        await self._session.flush()
        return _reading_to_domain(row)

    async def get_raw_readings(
        self, *, location_id: int, start_date: date, end_date: date
    ) -> list[RawWeatherReading]:
        stmt = (
            select(WeatherReadingRawModel)
            .where(
                WeatherReadingRawModel.location_id == location_id,
                WeatherReadingRawModel.valid_date >= start_date,
                WeatherReadingRawModel.valid_date <= end_date,
            )
            .order_by(WeatherReadingRawModel.valid_date)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_reading_to_domain(row) for row in rows]

    async def save_intelligence(
        self, record: DailyIntelligenceRecord
    ) -> DailyIntelligenceRecord:
        row = WeatherIntelligenceDailyModel(
            location_id=record.location_id,
            date=record.date,
            risk_level=record.risk_level,
            risk_factors=record.risk_factors,
            activity_scores=record.activity_scores,
            packing=record.packing,
            travel_advisory=record.travel_advisory,
            rule_config_version=record.rule_config_version,
            generated_at=record.generated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _intelligence_to_domain(row)

    async def get_fresh_intelligence(
        self,
        *,
        location_id: int,
        start_date: date,
        end_date: date,
        rule_config_version: str,
        fresh_since: datetime,
    ) -> list[DailyIntelligenceRecord]:
        stmt = (
            select(WeatherIntelligenceDailyModel)
            .where(
                WeatherIntelligenceDailyModel.location_id == location_id,
                WeatherIntelligenceDailyModel.date >= start_date,
                WeatherIntelligenceDailyModel.date <= end_date,
                WeatherIntelligenceDailyModel.rule_config_version == rule_config_version,
                WeatherIntelligenceDailyModel.generated_at >= fresh_since,
            )
            .order_by(WeatherIntelligenceDailyModel.date)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_intelligence_to_domain(row) for row in rows]
