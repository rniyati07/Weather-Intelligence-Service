"""Intelligence endpoints — API Spec §8.1, §8.2, §8.3.

Controllers stay thin: authenticate, validate, delegate to the use case,
project, wrap in the envelope. All computation already happened in Phases
5-7. Best-days and packing are *projections* of the same
`GetWeatherIntelligence` result — the guide forbids recomputing them.
"""

from fastapi import APIRouter, status

from app.interface.http.dependencies import (
    ApiKeyDep,
    CoordinatesDep,
    DateRangeDep,
    RateLimitDep,
    RequestIdDep,
    WeatherIntelligenceUseCaseDep,
)
from app.interface.http.envelope import success_envelope
from app.interface.http.schemas.common import ResponseEnvelope
from app.interface.http.schemas.intelligence import (
    BestDaysViewSchema,
    PackingViewSchema,
    WeatherIntelligenceSchema,
)

router = APIRouter(prefix="/locations/{location_id}", tags=["intelligence"])

_ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    status.HTTP_400_BAD_REQUEST: {"description": "Invalid coordinates or date range."},
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Per-key rate limit exceeded."},
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "All weather providers unavailable and no stored data."
    },
}


@router.get(
    "/intelligence",
    response_model=ResponseEnvelope[WeatherIntelligenceSchema],
    summary="Get weather intelligence",
    description=(
        "Full deterministic weather intelligence — per-day risk, activity suitability, "
        "packing, and a trip summary — for a location and inclusive date range. "
        "`narrative` is always `null` here; narration is a separate call."
    ),
    responses=_ERROR_RESPONSES,
)
async def get_intelligence(
    coordinates: CoordinatesDep,
    date_range: DateRangeDep,
    use_case: WeatherIntelligenceUseCaseDep,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
) -> ResponseEnvelope[WeatherIntelligenceSchema]:
    result = await use_case.execute(
        latitude=coordinates.latitude,
        longitude=coordinates.longitude,
        start=date_range.start,
        end=date_range.end,
    )
    return success_envelope(
        WeatherIntelligenceSchema.from_domain(result.intelligence),
        request_id=request_id,
        cache_status=result.cache_status,  # type: ignore[arg-type]
        rule_config_version=result.intelligence.rule_config_version,
        degraded=result.degraded,
    )


@router.get(
    "/intelligence/best-days",
    response_model=ResponseEnvelope[BestDaysViewSchema],
    summary="Get best and worst days",
    description=(
        "Trip-level ranking view: the best and worst days to travel plus the overall "
        "risk level. A projection of the same computation as `/intelligence`."
    ),
    responses=_ERROR_RESPONSES,
)
async def get_best_days(
    coordinates: CoordinatesDep,
    date_range: DateRangeDep,
    use_case: WeatherIntelligenceUseCaseDep,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
) -> ResponseEnvelope[BestDaysViewSchema]:
    result = await use_case.execute(
        latitude=coordinates.latitude,
        longitude=coordinates.longitude,
        start=date_range.start,
        end=date_range.end,
    )
    return success_envelope(
        BestDaysViewSchema.from_domain(result.intelligence),
        request_id=request_id,
        cache_status=result.cache_status,  # type: ignore[arg-type]
        rule_config_version=result.intelligence.rule_config_version,
        degraded=result.degraded,
    )


@router.get(
    "/intelligence/packing",
    response_model=ResponseEnvelope[PackingViewSchema],
    summary="Get packing recommendations",
    description=(
        "Aggregated, deduplicated packing list for the whole trip, in a stable "
        "configured order. A projection of the same computation as `/intelligence`."
    ),
    responses=_ERROR_RESPONSES,
)
async def get_packing(
    coordinates: CoordinatesDep,
    date_range: DateRangeDep,
    use_case: WeatherIntelligenceUseCaseDep,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
) -> ResponseEnvelope[PackingViewSchema]:
    result = await use_case.execute(
        latitude=coordinates.latitude,
        longitude=coordinates.longitude,
        start=date_range.start,
        end=date_range.end,
    )
    return success_envelope(
        PackingViewSchema.from_domain(result.intelligence),
        request_id=request_id,
        cache_status=result.cache_status,  # type: ignore[arg-type]
        rule_config_version=result.intelligence.rule_config_version,
        degraded=result.degraded,
    )
