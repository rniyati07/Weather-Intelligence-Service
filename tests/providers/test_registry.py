"""Unit tests for `ProviderRegistry`: selection, fallback, health, and routing.

Uses small scripted `WeatherProvider` test doubles rather than the real
adapters — no network involved. (A reusable, shared `FakeProvider` fixture
is Phase 11's job; these are ordinary test-local doubles.)
"""

from datetime import date

import httpx
import pytest

from app.domain.entities.weather import NormalizedReading, WeatherCondition
from app.domain.ports.provider_registry import AllProvidersFailedError
from app.domain.ports.weather_provider import DataClass, WeatherProvider
from app.infrastructure.providers.base import ProviderError
from app.infrastructure.providers.health import HealthTracker, ProviderStatus
from app.infrastructure.providers.registry import ProviderRegistry

_READING = NormalizedReading(
    date=date(2026, 8, 1),
    temp_min_c=24.0,
    temp_max_c=30.0,
    precipitation_probability=0.1,
    wind_speed_kph=10.0,
    condition=WeatherCondition.CLEAR,
    completeness=1.0,
    source_class="forecast",
)


class _ScriptedProvider(WeatherProvider):
    """A `WeatherProvider` double that always fails, always succeeds, or is unconfigured."""

    def __init__(
        self,
        name: str,
        data_class: DataClass,
        *,
        configured: bool = True,
        fails: bool = False,
    ) -> None:
        self.name = name
        self.data_class = data_class
        self._configured = configured
        self._fails = fails
        self.call_count = 0

    def is_configured(self) -> bool:
        return self._configured

    async def fetch(
        self, lat: float, lon: float, start: date, end: date
    ) -> list[NormalizedReading]:
        self.call_count += 1
        if self._fails:
            raise ProviderError(self.name, "simulated failure")
        return [_READING]


def _registry(
    providers: list[WeatherProvider],
    *,
    priority_forecast: list[str] | None = None,
    priority_historical: list[str] | None = None,
    health: HealthTracker | None = None,
) -> ProviderRegistry:
    return ProviderRegistry(
        providers,
        priority_forecast=priority_forecast or ["open_meteo", "openweather", "weatherapi"],
        priority_historical=priority_historical or ["meteostat"],
        health=health or HealthTracker(ttl_seconds=60),
        client=httpx.AsyncClient(),
    )


class TestSelect:
    def test_yields_in_priority_order(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        registry = _registry([fallback, primary])  # registered out of priority order

        selected = list(registry.select(DataClass.FORECAST))

        assert [p.name for p in selected] == ["open_meteo", "openweather"]

    def test_unconfigured_provider_is_skipped(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, configured=False)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        registry = _registry([primary, fallback])

        selected = list(registry.select(DataClass.FORECAST))

        assert [p.name for p in selected] == ["openweather"]

    def test_forecast_never_selects_historical_provider(self) -> None:
        forecast_provider = _ScriptedProvider("open_meteo", DataClass.FORECAST)
        historical_provider = _ScriptedProvider("meteostat", DataClass.HISTORICAL)
        registry = _registry([forecast_provider, historical_provider])

        selected = list(registry.select(DataClass.FORECAST))

        assert all(p.data_class == DataClass.FORECAST for p in selected)
        assert "meteostat" not in [p.name for p in selected]

    def test_forecast_never_selects_historical_even_if_misconfigured(self) -> None:
        # Meteostat accidentally listed under the forecast priority: the
        # registry must still refuse it, since it filters by the provider's
        # own `data_class`, not just configuration.
        historical_provider = _ScriptedProvider("meteostat", DataClass.HISTORICAL)
        registry = _registry(
            [historical_provider],
            priority_forecast=["meteostat"],
            priority_historical=["meteostat"],
        )

        assert list(registry.select(DataClass.FORECAST)) == []


class TestFetchWithFallback:
    async def test_primary_success_used_fallback_false(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST)
        registry = _registry([primary])

        result = await registry.fetch_with_fallback(
            DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
        )

        assert result.used_fallback is False
        assert result.readings == [_READING]

    async def test_primary_fails_second_succeeds_used_fallback_true(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, fails=True)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        registry = _registry([primary, fallback])

        result = await registry.fetch_with_fallback(
            DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
        )

        assert result.used_fallback is True
        assert result.readings == [_READING]
        assert primary.call_count == 1
        assert fallback.call_count == 1

    async def test_all_providers_failing_raises_all_providers_failed(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, fails=True)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST, fails=True)
        registry = _registry([primary, fallback])

        with pytest.raises(AllProvidersFailedError):
            await registry.fetch_with_fallback(
                DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
            )

    async def test_unconfigured_provider_is_never_attempted(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, configured=False)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        registry = _registry([primary, fallback])

        await registry.fetch_with_fallback(
            DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
        )

        assert primary.call_count == 0

    async def test_health_reflects_real_outcomes(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, fails=True)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        health = HealthTracker(ttl_seconds=60)
        registry = _registry(
            [primary, fallback],
            priority_forecast=["open_meteo", "openweather"],
            health=health,
        )

        await registry.fetch_with_fallback(
            DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
        )

        assert health.status("open_meteo") == ProviderStatus.DEGRADED
        assert health.status("openweather") == ProviderStatus.AVAILABLE

    async def test_unhealthy_provider_is_skipped_by_select(self) -> None:
        primary = _ScriptedProvider("open_meteo", DataClass.FORECAST, fails=True)
        fallback = _ScriptedProvider("openweather", DataClass.FORECAST)
        health = HealthTracker(ttl_seconds=60)
        registry = _registry(
            [primary, fallback],
            priority_forecast=["open_meteo", "openweather"],
            health=health,
        )

        # Two consecutive failures escalate open_meteo to UNAVAILABLE.
        health.record_failure("open_meteo")
        health.record_failure("open_meteo")

        result = await registry.fetch_with_fallback(
            DataClass.FORECAST, 15.25, 74.125, date(2026, 8, 1), date(2026, 8, 1)
        )

        assert primary.call_count == 0  # skipped, not attempted
        assert result.used_fallback is True


class TestProbeHealth:
    async def test_probe_updates_health_from_live_outcomes(self) -> None:
        healthy = _ScriptedProvider("open_meteo", DataClass.FORECAST)
        failing = _ScriptedProvider("openweather", DataClass.FORECAST, fails=True)
        unconfigured = _ScriptedProvider("weatherapi", DataClass.FORECAST, configured=False)
        registry = _registry([healthy, failing, unconfigured])

        snapshot = await registry.probe_health(15.25, 74.125, date(2026, 8, 1))

        assert snapshot["open_meteo"] == ProviderStatus.AVAILABLE
        assert snapshot["openweather"] == ProviderStatus.DEGRADED
        assert "weatherapi" not in snapshot  # never attempted: not configured
        assert unconfigured.call_count == 0
