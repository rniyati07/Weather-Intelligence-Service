"""Builders for the one response envelope every endpoint returns (API Spec §6).

Success and error responses share the same four keys — `success`, `data`,
`metadata`, `error` — so a consumer parses one shape. `Metadata` never
carries provider identity (API Spec §9.12).
"""

from datetime import UTC, datetime
from typing import TypeVar

from app.interface.http.schemas.common import (
    CacheStatus,
    ErrorCode,
    ErrorDetailSchema,
    ErrorEnvelope,
    ErrorSchema,
    MetadataSchema,
    ResponseEnvelope,
)

PayloadT = TypeVar("PayloadT")


def build_metadata(
    *,
    request_id: str,
    cache_status: CacheStatus | None = None,
    rule_config_version: str | None = None,
    degraded: bool | None = None,
) -> MetadataSchema:
    """Assemble response metadata. `generatedAt` is the only clock read here."""
    return MetadataSchema(
        generated_at=datetime.now(UTC),
        request_id=request_id,
        cache_status=cache_status,
        rule_config_version=rule_config_version,
        degraded=degraded,
    )


def success_envelope(
    data: PayloadT,
    *,
    request_id: str,
    cache_status: CacheStatus | None = None,
    rule_config_version: str | None = None,
    degraded: bool | None = None,
) -> ResponseEnvelope[PayloadT]:
    """A `2xx` envelope. Degraded success is still `success: true` (API Spec §6).

    The payload type flows through to the return type, so each route's
    declared `ResponseEnvelope[...]` is checked against what it actually
    passes here.
    """
    return ResponseEnvelope[PayloadT](
        success=True,
        data=data,
        metadata=build_metadata(
            request_id=request_id,
            cache_status=cache_status,
            rule_config_version=rule_config_version,
            degraded=degraded,
        ),
        error=None,
    )


def error_envelope(
    *,
    code: ErrorCode,
    message: str,
    request_id: str,
    details: list[ErrorDetailSchema] | None = None,
) -> ErrorEnvelope:
    """A failure envelope: `data` is null and the error object carries the code."""
    return ErrorEnvelope(
        success=False,
        data=None,
        metadata=build_metadata(request_id=request_id),
        error=ErrorSchema(code=code, message=message, details=details),
    )
