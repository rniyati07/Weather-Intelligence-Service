"""`ProviderRegistryPort`: routes a fetch across configured providers with fallback.

Implemented by `infrastructure.providers.registry.ProviderRegistry`. Use
cases (Phase 7/9) depend on this port, never a concrete registry or adapter
directly. Provider independence is a hard rule (guide §5.3): identity never
crosses this boundary into anything an API consumer sees — only into logs,
`weather_readings_raw.provider` (Phase 3), and `GET /providers/health`
(Phase 9).
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from app.domain.entities.weather import NormalizedReading
from app.domain.ports.weather_provider import DataClass, WeatherProvider


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Readings from the first provider that succeeded, plus whether it was a fallback."""

    readings: list[NormalizedReading]
    used_fallback: bool


class AllProvidersFailedError(Exception):
    """Raised when every provider for `data_class` failed, was unhealthy, or unconfigured.

    The caller (a Phase 7/9 use case) decides between serving stale stored
    data or returning `503 PROVIDER_UNAVAILABLE` — the registry itself never
    makes that call.
    """

    def __init__(self, data_class: DataClass) -> None:
        self.data_class = data_class
        super().__init__(f"All providers failed for data class '{data_class.value}'")


class ProviderRegistryPort(ABC):
    """Selects providers by data class, priority, and health; fetches with fallback."""

    @abstractmethod
    def select(
        self, data_class: DataClass, *, exclude: set[str] | None = None
    ) -> Iterator[WeatherProvider]:
        """Yield configured, healthy providers for `data_class`, in priority order.

        A forecast request never yields a `HISTORICAL` provider (and vice
        versa) — routing is enforced structurally, not just by configuration.
        """

    @abstractmethod
    async def fetch_with_fallback(
        self, data_class: DataClass, lat: float, lon: float, start: date, end: date
    ) -> FetchResult:
        """Try providers for `data_class` in priority order until one succeeds.

        Raises `AllProvidersFailedError` if the chain is exhausted.
        """
