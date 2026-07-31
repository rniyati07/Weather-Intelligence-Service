"""Provider health endpoint — API Spec §8.6 (operators only).

The single endpoint that names providers, by design and by documented
exception. It requires an operator key from `OPS_API_KEYS`, and reads only
the registry's cached health — it never issues an upstream call.
"""

from fastapi import APIRouter, status

from app.interface.http.dependencies import (
    OpsApiKeyDep,
    ProviderHealthUseCaseDep,
    RequestIdDep,
)
from app.interface.http.envelope import success_envelope
from app.interface.http.schemas.common import ResponseEnvelope
from app.interface.http.schemas.providers import ProviderHealthSchema, ProviderHealthViewSchema

router = APIRouter(prefix="/providers", tags=["operations"])


@router.get(
    "/health",
    response_model=ResponseEnvelope,
    summary="Get provider health",
    description=(
        "Operational availability of each upstream weather provider. Restricted to "
        "operator keys (`OPS_API_KEYS`). This is the only endpoint that names "
        "providers; weather data responses are always provider-agnostic."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
        status.HTTP_403_FORBIDDEN: {"description": "Key is not permitted for operator endpoints."},
    },
)
async def get_provider_health(
    use_case: ProviderHealthUseCaseDep,
    request_id: RequestIdDep,
    _ops_key: OpsApiKeyDep,
) -> ResponseEnvelope:
    entries = use_case.execute()
    view = ProviderHealthViewSchema(
        providers=[
            ProviderHealthSchema(
                provider=entry.provider,
                status=entry.status,
                last_checked_at=entry.last_checked_at,
            )
            for entry in entries
        ]
    )
    return success_envelope(view, request_id=request_id)
