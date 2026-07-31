"""Narration endpoint — API Spec §8.5.

The only endpoint that invokes the AI layer, and the only one with a request
body. Narration is mandatory in this service (Phase 8 refactor), so an LLM
failure surfaces as `503 SERVICE_DEGRADED` rather than a templated fallback.
"""

from fastapi import APIRouter, status

from app.interface.http.dependencies import (
    ApiKeyDep,
    CoordinatesDep,
    GenerateNarrativeUseCaseDep,
    RateLimitDep,
    RequestIdDep,
    SettingsDep,
    validate_date_range,
)
from app.interface.http.envelope import success_envelope
from app.interface.http.errors import ValidationFailedError
from app.interface.http.schemas.common import ErrorDetailSchema, ResponseEnvelope
from app.interface.http.schemas.intelligence import (
    NarrativeSchema,
    NarrativeViewSchema,
    location_from_domain,
    period_from_domain,
)
from app.interface.http.schemas.narrative import SUPPORTED_LANGUAGES, NarrativeRequestSchema

router = APIRouter(prefix="/locations/{location_id}", tags=["narrative"])


@router.post(
    "/intelligence/narrative",
    response_model=ResponseEnvelope,
    summary="Generate an AI narrative",
    description=(
        "Natural-language restatement of the deterministic intelligence for a location "
        "and date range. The AI only describes values that were already computed — it "
        "never creates or alters a risk level, score, ranking, or recommendation."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid body, coordinates, or language."},
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
        status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Per-key rate limit exceeded."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Narration or weather data is temporarily unavailable."
        },
    },
)
async def generate_narrative(
    coordinates: CoordinatesDep,
    body: NarrativeRequestSchema,
    use_case: GenerateNarrativeUseCaseDep,
    settings: SettingsDep,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
) -> ResponseEnvelope:
    if body.language not in SUPPORTED_LANGUAGES:
        raise ValidationFailedError(
            f"Unsupported language '{body.language}'.",
            details=[
                ErrorDetailSchema(
                    field="language",
                    issue=f"supported languages: {', '.join(sorted(SUPPORTED_LANGUAGES))}",
                )
            ],
        )

    # Same cross-field date rules as the GET endpoints, applied to the body.
    date_range = validate_date_range(body.start_date, body.end_date, settings)

    result = await use_case.execute(
        latitude=coordinates.latitude,
        longitude=coordinates.longitude,
        start=date_range.start,
        end=date_range.end,
        language=body.language,
    )
    view = NarrativeViewSchema(
        location=location_from_domain(result.location),
        period=period_from_domain(result.period),
        narrative=NarrativeSchema.from_domain(result.narrative),
    )
    return success_envelope(
        view,
        request_id=request_id,
        cache_status=result.cache_status,  # type: ignore[arg-type]
        rule_config_version=result.rule_config_version,
        degraded=result.degraded,
    )
