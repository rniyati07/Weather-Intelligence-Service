"""Narration request body — API Spec §9.10.

The only request body in the API. Field-level shape is validated here;
cross-field rules (`startDate <= endDate`, horizon limits) are applied by the
shared validator in `dependencies.py` so GET and POST enforce them identically.
"""

from datetime import date

from pydantic import Field

from app.interface.http.schemas.common import CamelModel

#: v1 supports English only (API Spec §11 "Language").
SUPPORTED_LANGUAGES = frozenset({"en"})


class NarrativeRequestSchema(CamelModel):
    """API Spec §9.10 `NarrativeRequest`."""

    start_date: date = Field(..., description="Inclusive range start (YYYY-MM-DD).")
    end_date: date = Field(..., description="Inclusive range end (YYYY-MM-DD).")
    language: str = Field(default="en", description="Narration language; v1 supports 'en'.")
