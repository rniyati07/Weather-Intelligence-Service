"""`WeatherRepository` port: the persistence contract for readings and intelligence.

Implemented by `infrastructure.persistence.repositories`. Only the domain
records in `domain/entities/persistence.py` cross this boundary — never ORM
models. Freshness is expressed as an explicit cutoff (`fresh_since`) supplied
by the caller rather than computed here, so the port stays free of a clock.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime

from app.domain.entities.persistence import DailyIntelligenceRecord, Location, RawWeatherReading


class WeatherRepository(ABC):
    """Persists locations, raw provider readings, and computed daily intelligence."""

    @abstractmethod
    async def get_or_create_location(
        self, *, name: str, latitude: float, longitude: float, normalized_key: str
    ) -> Location:
        """Return the location for `normalized_key`, creating it if absent."""

    @abstractmethod
    async def save_raw_reading(self, reading: RawWeatherReading) -> RawWeatherReading:
        """Persist one provider reading and return it with its assigned id."""

    @abstractmethod
    async def get_raw_readings(
        self, *, location_id: int, start_date: date, end_date: date
    ) -> list[RawWeatherReading]:
        """Return stored readings for a location within an inclusive date range."""

    @abstractmethod
    async def save_intelligence(
        self, record: DailyIntelligenceRecord
    ) -> DailyIntelligenceRecord:
        """Persist one computed daily intelligence row and return it with its assigned id."""

    @abstractmethod
    async def get_fresh_intelligence(
        self,
        *,
        location_id: int,
        start_date: date,
        end_date: date,
        rule_config_version: str,
        fresh_since: datetime,
    ) -> list[DailyIntelligenceRecord]:
        """Return rows matching `rule_config_version`, generated at/after `fresh_since`."""
