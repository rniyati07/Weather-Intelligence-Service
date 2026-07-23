"""`WeatherProvider` port: one contract every adapter implements.

Adapters (`infrastructure/providers/*.py`) are the only modules aware of a
provider's request format or response shape. They translate exactly one
external dialect into `NormalizedReading` objects — they must not compute,
cache, or decide (that's the registry's job in Phase 5, and the engines' in
Phase 7).
"""

from abc import ABC, abstractmethod
from datetime import date
from enum import StrEnum

from app.domain.entities.weather import NormalizedReading


class DataClass(StrEnum):
    """Routes provider selection: a forecast request can never fall back to
    a historical source (guide §5)."""

    FORECAST = "forecast"
    HISTORICAL = "historical"


class WeatherProvider(ABC):
    """A single external weather data source, behind one uniform contract."""

    name: str
    data_class: DataClass

    @abstractmethod
    def is_configured(self) -> bool:
        """Return False when a required API key is absent.

        The registry (Phase 5) skips an unconfigured provider rather than
        treating it as a failure. Open-Meteo needs no key, so it always
        returns True.
        """

    @abstractmethod
    async def fetch(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[NormalizedReading]:
        """Fetch and normalize readings for `[start, end]` at `(lat, lon)`.

        A day this provider cannot supply or validate is simply absent from
        the result — never fabricated, never a partial/invalid reading.
        """
