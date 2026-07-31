"""Raw weather endpoint — API Spec §8.4.

Returns the internal normalized reading model with no intelligence applied
and, critically, no provider identified (guide §5.3).
"""

from fastapi import APIRouter, status

from app.domain.entities.weather_intelligence import Period, ResolvedLocation
from app.interface.http.dependencies import (
    ApiKeyDep,
    CoordinatesDep,
    DateRangeDep,
    RateLimitDep,
    RawWeatherUseCaseDep,
    RequestIdDep,
)
from app.interface.http.envelope import success_envelope
from app.interface.http.schemas.common import ResponseEnvelope
from app.interface.http.schemas.weather import RawWeatherViewSchema

router = APIRouter(prefix="/locations/{location_id}", tags=["weather"])


@router.get(
    "/weather/raw",
    response_model=ResponseEnvelope[RawWeatherViewSchema],
    summary="Get raw normalized weather",
    description=(
        "Provider-normalized daily weather readings for a location and inclusive date "
        "range, without any intelligence processing. The response never identifies "
        "which upstream provider supplied the data."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid coordinates or date range."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Per-key rate limit exceeded."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "All weather providers unavailable and no stored data."
        },
    },
)
async def get_raw_weather(
    coordinates: CoordinatesDep,
    date_range: DateRangeDep,
    use_case: RawWeatherUseCaseDep,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
) -> ResponseEnvelope[RawWeatherViewSchema]:
    result = await use_case.execute(
        latitude=coordinates.latitude,
        longitude=coordinates.longitude,
        start=date_range.start,
        end=date_range.end,
    )
    view = RawWeatherViewSchema.from_domain(
        ResolvedLocation(
            id=f"{coordinates.latitude},{coordinates.longitude}",
            latitude=coordinates.latitude,
            longitude=coordinates.longitude,
        ),
        Period(start_date=date_range.start, end_date=date_range.end),
        result.readings,
    )
    return success_envelope(
        view,
        request_id=request_id,
        cache_status=result.cache_status,  # type: ignore[arg-type]
        degraded=result.degraded,
    )
