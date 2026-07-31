"""Shared FastAPI dependencies: settings, DB session, auth, validation, use cases.

This module is the composition root. It is the only place that knows both
the domain ports and their infrastructure implementations, which is what
keeps `application/` free of infrastructure imports (guide §3.1) while still
letting routes receive fully-wired use cases.

Validation here runs *before* any provider or database call (API Spec §11).
"""

import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import Depends, Header, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.generate_narrative import GenerateNarrative
from app.application.use_cases.get_provider_health import GetProviderHealth
from app.application.use_cases.get_raw_weather import GetRawWeather
from app.application.use_cases.get_weather_intelligence import GetWeatherIntelligence
from app.application.use_cases.load_readings import WeatherReadingsLoader
from app.domain.ports.narration import NarrationPort
from app.domain.ports.provider_registry import ProviderRegistryPort
from app.domain.ports.repository import WeatherRepository
from app.infrastructure.ai.narration_service import get_narration_service
from app.infrastructure.config.rule_config_loader import get_rule_config
from app.infrastructure.config.settings import Settings, get_settings
from app.infrastructure.persistence.repositories import SqlAlchemyWeatherRepository
from app.infrastructure.persistence.session import get_database
from app.infrastructure.providers.registry import get_provider_registry
from app.interface.http.errors import (
    AuthenticationFailedError,
    AuthorizationFailedError,
    RateLimitedError,
    ValidationFailedError,
)
from app.interface.http.schemas.common import ErrorDetailSchema

_MIN_LATITUDE, _MAX_LATITUDE = -90.0, 90.0
_MIN_LONGITUDE, _MAX_LONGITUDE = -180.0, 180.0
_RATE_LIMIT_WINDOW_SECONDS = 60


def get_app_settings() -> Settings:
    """FastAPI dependency returning the process-wide, cached `Settings`."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_request_id(request: Request) -> str:
    """The correlation id bound by `RequestContextMiddleware` (Phase 2).

    Surfaces on every response as `metadata.requestId` (API Spec §9.12), so
    one request is traceable from client report to server log.
    """
    request_id: str = request.state.request_id
    return request_id


RequestIdDep = Annotated[str, Depends(get_request_id)]


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """One session per request: commits on success, rolls back on exception."""
    async with get_database().session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_weather_repository(session: DbSessionDep) -> WeatherRepository:
    """FastAPI dependency returning a `WeatherRepository` bound to the request's session."""
    return SqlAlchemyWeatherRepository(session)


WeatherRepositoryDep = Annotated[WeatherRepository, Depends(get_weather_repository)]


def get_provider_registry_dependency() -> ProviderRegistryPort:
    """FastAPI dependency returning the process-wide, cached `ProviderRegistry`."""
    return get_provider_registry()


ProviderRegistryDep = Annotated[ProviderRegistryPort, Depends(get_provider_registry_dependency)]


def get_narration_service_dependency() -> NarrationPort:
    """FastAPI dependency returning the process-wide, cached `NarrationService`."""
    return get_narration_service()


NarrationServiceDep = Annotated[NarrationPort, Depends(get_narration_service_dependency)]


# --------------------------------------------------------------------------
# Authentication (API Spec §3, §7.1)
# --------------------------------------------------------------------------


def require_api_key(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Reject any request without a recognised consumer key (`401`)."""
    if not x_api_key or x_api_key not in settings.api_keys:
        raise AuthenticationFailedError("Missing or invalid API key.")
    return x_api_key


ApiKeyDep = Annotated[str, Depends(require_api_key)]


def require_ops_api_key(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> str:
    """Restrict operator-only routes to `OPS_API_KEYS` (`401` unknown, `403` not permitted)."""
    if not x_api_key:
        raise AuthenticationFailedError("Missing or invalid API key.")
    if x_api_key in settings.ops_api_keys:
        return x_api_key
    if x_api_key in settings.api_keys:
        raise AuthorizationFailedError("This API key is not permitted for operator endpoints.")
    raise AuthenticationFailedError("Missing or invalid API key.")


OpsApiKeyDep = Annotated[str, Depends(require_ops_api_key)]


# --------------------------------------------------------------------------
# Rate limiting (guide §Phase 9 step 8)
# --------------------------------------------------------------------------

#: Per-key request timestamps within the rolling window. In-process by design:
#: a shared limiter needs Redis, which the TRD defers to V2 (§7.4).
_request_times: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(api_key: ApiKeyDep, settings: SettingsDep) -> None:
    """Reject a key exceeding `RATE_LIMIT_PER_MINUTE` with `429` + `Retry-After`."""
    now = time.monotonic()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    seen = _request_times[api_key]
    while seen and seen[0] < window_start:
        seen.popleft()

    if len(seen) >= settings.rate_limit_per_minute:
        retry_after = max(1, int(_RATE_LIMIT_WINDOW_SECONDS - (now - seen[0])))
        raise RateLimitedError(
            "Rate limit exceeded. Please retry shortly.", retry_after_seconds=retry_after
        )
    seen.append(now)


RateLimitDep = Annotated[None, Depends(enforce_rate_limit)]


def reset_rate_limiter() -> None:
    """Clear all rate-limit state. Test-support only."""
    _request_times.clear()


# --------------------------------------------------------------------------
# Request validation (API Spec §11) — runs before any provider or DB call
# --------------------------------------------------------------------------


class Coordinates:
    """A validated `"{lat},{lon}"` path parameter."""

    __slots__ = ("latitude", "longitude")

    def __init__(self, latitude: float, longitude: float) -> None:
        self.latitude = latitude
        self.longitude = longitude


def parse_location_id(
    location_id: Annotated[
        str, Path(description='Coordinate id, `"{lat},{lon}"` — e.g. `15.2993,74.1240`.')
    ],
) -> Coordinates:
    """Parse and range-check `locationId` (`400` on anything malformed)."""
    parts = location_id.split(",")
    if len(parts) != 2:
        raise ValidationFailedError(
            "locationId must be in the form '{lat},{lon}'.",
            details=[ErrorDetailSchema(field="locationId", issue="expected '{lat},{lon}'")],
        )
    try:
        latitude, longitude = float(parts[0]), float(parts[1])
    except ValueError:
        raise ValidationFailedError(
            "locationId coordinates must be numeric.",
            details=[ErrorDetailSchema(field="locationId", issue="coordinates are not numeric")],
        ) from None

    issues: list[ErrorDetailSchema] = []
    if not (_MIN_LATITUDE <= latitude <= _MAX_LATITUDE):
        issues.append(
            ErrorDetailSchema(field="locationId", issue="latitude must be within -90..90")
        )
    if not (_MIN_LONGITUDE <= longitude <= _MAX_LONGITUDE):
        issues.append(
            ErrorDetailSchema(field="locationId", issue="longitude must be within -180..180")
        )
    if issues:
        raise ValidationFailedError("locationId coordinates are out of range.", details=issues)

    return Coordinates(latitude, longitude)


CoordinatesDep = Annotated[Coordinates, Depends(parse_location_id)]


class DateRange:
    """A validated, inclusive request date range."""

    __slots__ = ("start", "end")

    def __init__(self, start: date, end: date) -> None:
        self.start = start
        self.end = end


def validate_date_range(start: date, end: date, settings: Settings) -> DateRange:
    """Apply the §11 cross-field date rules shared by every endpoint."""
    if end < start:
        raise ValidationFailedError(
            "endDate must be on or after startDate.",
            details=[ErrorDetailSchema(field="endDate", issue="endDate is before startDate")],
        )

    span_days = (end - start).days + 1
    horizon = settings.max_forecast_horizon_days
    if span_days > horizon:
        raise ValidationFailedError(
            f"The requested range exceeds the maximum of {horizon} days.",
            details=[
                ErrorDetailSchema(field="endDate", issue=f"range spans {span_days} days")
            ],
        )

    days_ahead = (end - datetime.now(UTC).date()).days
    if days_ahead > horizon:
        raise ValidationFailedError(
            f"endDate is beyond the supported {horizon}-day forecast window.",
            details=[
                ErrorDetailSchema(field="endDate", issue=f"{days_ahead} days beyond today")
            ],
        )

    return DateRange(start, end)


_StartDateQuery = Annotated[date, Query(alias="startDate", description="Inclusive start.")]
_EndDateQuery = Annotated[date, Query(alias="endDate", description="Inclusive end.")]


def parse_date_range(
    settings: SettingsDep, start_date: _StartDateQuery, end_date: _EndDateQuery
) -> DateRange:
    """Query-parameter date range for the `GET` endpoints."""
    return validate_date_range(start_date, end_date, settings)


DateRangeDep = Annotated[DateRange, Depends(parse_date_range)]


# --------------------------------------------------------------------------
# Use cases — assembled from ports plus their infrastructure implementations
# --------------------------------------------------------------------------


def get_readings_loader(
    repository: WeatherRepositoryDep, registry: ProviderRegistryDep, settings: SettingsDep
) -> WeatherReadingsLoader:
    return WeatherReadingsLoader(
        repository=repository,
        registry=registry,
        provider_cache_ttl_seconds=settings.cache_ttl_provider_seconds,
    )


ReadingsLoaderDep = Annotated[WeatherReadingsLoader, Depends(get_readings_loader)]


def get_weather_intelligence_use_case(
    loader: ReadingsLoaderDep, repository: WeatherRepositoryDep, settings: SettingsDep
) -> GetWeatherIntelligence:
    return GetWeatherIntelligence(
        loader=loader,
        repository=repository,
        rule_config=get_rule_config(settings.rule_config_version),
    )


WeatherIntelligenceUseCaseDep = Annotated[
    GetWeatherIntelligence, Depends(get_weather_intelligence_use_case)
]


def get_raw_weather_use_case(loader: ReadingsLoaderDep) -> GetRawWeather:
    return GetRawWeather(loader=loader)


RawWeatherUseCaseDep = Annotated[GetRawWeather, Depends(get_raw_weather_use_case)]


def get_generate_narrative_use_case(
    intelligence: WeatherIntelligenceUseCaseDep, narration: NarrationServiceDep
) -> GenerateNarrative:
    return GenerateNarrative(intelligence_use_case=intelligence, narration=narration)


GenerateNarrativeUseCaseDep = Annotated[
    GenerateNarrative, Depends(get_generate_narrative_use_case)
]


def get_provider_health_use_case(registry: ProviderRegistryDep) -> GetProviderHealth:
    return GetProviderHealth(registry=registry)


ProviderHealthUseCaseDep = Annotated[GetProviderHealth, Depends(get_provider_health_use_case)]
