"""Shared HTTP schema building blocks: envelope, metadata, errors, location, period.

Every model here is external-facing and therefore **camelCase** (API Spec §9),
while the domain stays snake_case — the `alias_generator` is what bridges the
two, per guide §Phase 9 step 1. `populate_by_name=True` lets these be built
from snake_case domain attributes while serialising to camelCase.
"""

from datetime import date, datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

#: Contract version reported on every response (API Spec §9.12).
API_VERSION = "1.0"

ErrorCode = Literal[
    "VALIDATION_ERROR",
    "AUTHENTICATION_ERROR",
    "AUTHORIZATION_ERROR",
    "NOT_FOUND",
    "RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "UPSTREAM_TIMEOUT",
    "SERVICE_DEGRADED",
    "INTERNAL_ERROR",
]
CacheStatus = Literal["hit", "miss", "stale"]


class CamelModel(BaseModel):
    """Base for every external schema: snake_case internally, camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LocationSchema(CamelModel):
    """API Spec §9.2."""

    id: str
    latitude: float
    longitude: float
    name: str | None = None


class PeriodSchema(CamelModel):
    """API Spec §9.3."""

    start_date: date
    end_date: date


class ErrorDetailSchema(CamelModel):
    """API Spec §7.2 `ErrorDetail`."""

    field: str
    issue: str


class ErrorSchema(CamelModel):
    """API Spec §7.2. Never carries internal or provider detail."""

    code: ErrorCode
    message: str
    details: list[ErrorDetailSchema] | None = None


class MetadataSchema(CamelModel):
    """API Spec §9.12. Intentionally contains **no** provider identity."""

    api_version: str = API_VERSION
    generated_at: datetime
    request_id: str
    cache_status: CacheStatus | None = None
    rule_config_version: str | None = None
    degraded: bool | None = None


#: Payload type carried in `data`. Making the envelope generic is what lets
#: each route publish its concrete response schema in OpenAPI — an untyped
#: `data` erases the payload from the contract and breaks client codegen.
PayloadT = TypeVar("PayloadT")


class ResponseEnvelope(CamelModel, Generic[PayloadT]):
    """API Spec §6 — the one envelope every response uses, success or failure.

    Parameterised per endpoint (e.g. `ResponseEnvelope[WeatherIntelligenceSchema]`)
    so Swagger renders the real payload. The wire format is unchanged: the
    four keys and their values are exactly as before.
    """

    success: bool
    data: PayloadT | None
    metadata: MetadataSchema
    error: ErrorSchema | None = None


#: Failure responses carry no payload; `data` is always `null` (API Spec §6).
ErrorEnvelope = ResponseEnvelope[None]
