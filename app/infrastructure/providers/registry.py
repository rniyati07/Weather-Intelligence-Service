"""Provider registry: routes fetches by data class, priority, and health.

Owns selection, fallback, and health caching; the four Phase 4 adapters stay
dumb — each knows only how to talk to one external API. Provider identity
never leaves this module except into logs, the health snapshot, and (via
`weather_readings_raw.provider`, Phase 3) storage.
"""

import logging
from collections.abc import Iterator
from datetime import date
from functools import lru_cache

import httpx

from app.domain.ports.provider_registry import (
    AllProvidersFailedError,
    FetchResult,
    ProviderRegistryPort,
)
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.providers.base import ProviderError, ProviderTimeoutError, build_http_client
from app.infrastructure.providers.health import HealthTracker, ProviderStatus
from app.infrastructure.providers.meteostat import MeteostatAdapter
from app.infrastructure.providers.open_meteo import OpenMeteoAdapter
from app.infrastructure.providers.openweather import OpenWeatherAdapter
from app.infrastructure.providers.weatherapi import WeatherApiAdapter

logger = logging.getLogger(__name__)


class ProviderRegistry(ProviderRegistryPort):
    """Selects and calls providers for a given data class, in priority order."""

    def __init__(
        self,
        providers: list[WeatherProvider],
        *,
        priority_forecast: list[str],
        priority_historical: list[str],
        health: HealthTracker,
        client: httpx.AsyncClient,
    ) -> None:
        self._providers_by_name = {provider.name: provider for provider in providers}
        self._priority: dict[DataClass, list[str]] = {
            DataClass.FORECAST: priority_forecast,
            DataClass.HISTORICAL: priority_historical,
        }
        self._health = health
        self._client = client

    def _priority_list(self, data_class: DataClass) -> list[str]:
        # Only names actually registered *under this data class* survive —
        # this is what makes forecast/historical routing structural rather
        # than a matter of trusting `PROVIDER_PRIORITY_*` configuration.
        return [
            name
            for name in self._priority.get(data_class, [])
            if name in self._providers_by_name
            and self._providers_by_name[name].data_class == data_class
        ]

    def select(
        self, data_class: DataClass, *, exclude: set[str] | None = None
    ) -> Iterator[WeatherProvider]:
        excluded = exclude or set()
        for name in self._priority_list(data_class):
            if name in excluded:
                continue
            provider = self._providers_by_name[name]
            if not provider.is_configured():
                continue
            if self._health.status(name) is ProviderStatus.UNAVAILABLE:
                continue
            yield provider

    async def fetch_with_fallback(
        self, data_class: DataClass, lat: float, lon: float, start: date, end: date
    ) -> FetchResult:
        priority = self._priority_list(data_class)
        primary_name = priority[0] if priority else None

        for provider in self.select(data_class):
            try:
                readings = await provider.fetch(lat, lon, start, end)
            except (ProviderError, ProviderTimeoutError) as exc:
                logger.warning(
                    "provider_fetch_failed",
                    extra={"provider": provider.name, "error": str(exc)},
                )
                self._health.record_failure(provider.name)
                continue

            self._health.record_success(provider.name)
            # A fallback was used whenever the provider that actually served
            # this request wasn't the top of the priority chain — whether it
            # was bypassed just now (in-loop failure) or was already known
            # unconfigured/unhealthy before `select()` ever yielded it.
            return FetchResult(readings=readings, used_fallback=provider.name != primary_name)

        raise AllProvidersFailedError(data_class)

    async def probe_health(
        self, lat: float, lon: float, probe_date: date
    ) -> dict[str, ProviderStatus]:
        """Actively check every registered, configured provider now.

        Feeds `GET /providers/health` (Phase 9) — unlike `select()`, this
        makes real calls rather than trusting the cache, refreshing it as a
        side effect.
        """
        for provider in self._providers_by_name.values():
            if not provider.is_configured():
                continue
            try:
                await provider.fetch(lat, lon, probe_date, probe_date)
            except (ProviderError, ProviderTimeoutError):
                self._health.record_failure(provider.name)
            else:
                self._health.record_success(provider.name)

        return {name: record.status for name, record in self._health.snapshot().items()}

    async def aclose(self) -> None:
        """Close the shared HTTP client every adapter was constructed with."""
        await self._client.aclose()


def _build_providers(settings: Settings, client: httpx.AsyncClient) -> list[WeatherProvider]:
    attempts = settings.provider_retry_attempts
    backoff = settings.provider_retry_backoff_seconds
    return [
        OpenMeteoAdapter(client, retry_attempts=attempts, retry_backoff_seconds=backoff),
        OpenWeatherAdapter(
            client,
            api_key=settings.openweather_api_key,
            retry_attempts=attempts,
            retry_backoff_seconds=backoff,
        ),
        WeatherApiAdapter(
            client,
            api_key=settings.weatherapi_key,
            retry_attempts=attempts,
            retry_backoff_seconds=backoff,
        ),
        MeteostatAdapter(
            client,
            api_key=settings.meteostat_api_key,
            retry_attempts=attempts,
            retry_backoff_seconds=backoff,
        ),
    ]


def build_provider_registry(settings: Settings, client: httpx.AsyncClient) -> ProviderRegistry:
    """Wire the four Phase 4 adapters, Phase 2 settings, and a fresh `HealthTracker`."""
    return ProviderRegistry(
        _build_providers(settings, client),
        priority_forecast=list(settings.provider_priority_forecast),
        priority_historical=list(settings.provider_priority_historical),
        health=HealthTracker(ttl_seconds=settings.provider_health_ttl_seconds),
        client=client,
    )


@lru_cache
def get_provider_registry() -> ProviderRegistry:
    """Return the process-wide `ProviderRegistry`, constructed on first call."""
    settings = get_settings()
    client = build_http_client(settings.provider_timeout_seconds)
    return build_provider_registry(settings, client)
