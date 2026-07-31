"""Provider-health schemas — API Spec §9.11 (operational endpoint only).

This is the **one** place provider names legitimately appear (API Spec §8.6);
every weather-data payload stays provider-agnostic.
"""

from datetime import datetime

from app.interface.http.schemas.common import CamelModel


class ProviderHealthSchema(CamelModel):
    """API Spec §9.11."""

    provider: str
    status: str
    last_checked_at: datetime


class ProviderHealthViewSchema(CamelModel):
    """Payload of `GET /providers/health` (API Spec §8.6)."""

    providers: list[ProviderHealthSchema]
