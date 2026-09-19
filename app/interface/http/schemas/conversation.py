"""Conversation and Chat HTTP schemas.

`CamelModel`, not plain `BaseModel` — every other schema in this codebase
publishes camelCase field names on the wire (API Spec §9), and these were
the one place that didn't, which meant `POST /conversations/chat` returned
`trip_context`/`conversation_id`/`context_complete` while every other
endpoint returns `tripContext`/`conversationId`/... A frontend built against
the documented convention would have silently gotten the wrong shape from
exactly the endpoints it most needs (chat is the new primary surface).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.entities.attractions import Attraction
from app.domain.entities.trip import GeocodedPlace
from app.interface.http.schemas.common import CamelModel


class MessageSchema(CamelModel):
    """Single message in a conversation."""

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    metadata: dict[str, Any]
    created_at: datetime


class ConversationSchema(CamelModel):
    """Conversation with full context and messages."""

    id: UUID
    trip_context: dict[str, Any]
    messages: list[MessageSchema]
    created_at: datetime
    updated_at: datetime
    is_active: bool


class ConversationCreateRequest(CamelModel):
    """Request to create a new conversation."""

    initial_message: str | None = Field(None, description="First user message")


class ConversationCreateResponse(CamelModel):
    """Response after creating a conversation."""

    conversation: ConversationSchema


class ConversationListItem(CamelModel):
    """Conversation summary for list views."""

    id: UUID
    trip_context: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    message_count: int
    last_message_preview: str | None = None


class ChatRequest(CamelModel):
    """Chat message request."""

    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    conversation_id: UUID | None = Field(
        None, description="Existing conversation ID, or null to create new"
    )


class PlaceSchema(CamelModel):
    """A single real place backing a chat reply.

    Always sourced from a `PlacesPort` call and the deterministic
    weather-aware ranking in `attraction_matching.py` — never from Gemini.
    Deliberately excludes the provider's internal id (an OSM node/way
    reference) and per-day grouping: this is a flat, frontend-independent
    reference list, not a projection of the provider's own record shape.
    """

    name: str
    type: str = Field(description="AttractionType value, e.g. 'beach', 'museum'.")
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    weather_suitability: str = Field(
        description="WeatherSuitability value, e.g. 'ideal', 'poor'."
    )
    reason: str = Field(description="Deterministic, data-derived note on why this fits.")

    @classmethod
    def from_domain(cls, attraction: Attraction) -> "PlaceSchema":
        return cls(
            name=attraction.name,
            type=attraction.type.value,
            latitude=attraction.latitude,
            longitude=attraction.longitude,
            address=attraction.address,
            weather_suitability=attraction.weather_suitability.value,
            reason=attraction.weather_notes or "",
        )


class DestinationCandidateSchema(CamelModel):
    """One candidate location for an ambiguous destination mention.

    Structured form of the options listed in a clarification reply's
    `response` text — the frontend renders choices from this, never by
    parsing the message body.
    """

    name: str
    display_name: str
    latitude: float
    longitude: float
    country: str | None = None
    country_code: str | None = None
    admin1: str | None = None

    @classmethod
    def from_domain(cls, place: GeocodedPlace) -> "DestinationCandidateSchema":
        return cls(
            name=place.name,
            display_name=place.display_name,
            latitude=place.latitude,
            longitude=place.longitude,
            country=place.country,
            country_code=place.country_code,
            admin1=place.admin1,
        )


class ChatResponse(CamelModel):
    """Chat message response."""

    conversation_id: UUID
    response: str
    context_complete: bool
    missing_essentials: list[str]
    trip_context: dict[str, Any]
    intent: str = Field(description="ChatIntent value classified for this turn.")
    llm_generated: bool = Field(
        description="True when `response` came from Gemini; false for a deterministic "
        "template (clarification, date-range rejection, or an LLM-failure fallback)."
    )
    places: list[PlaceSchema] = Field(
        default_factory=list,
        description="Real places grounding this reply, from the backend Places provider. "
        "Empty when this turn fetched no attractions.",
    )
    destination_candidates: list[DestinationCandidateSchema] = Field(
        default_factory=list,
        description="Populated only when `response` is a destination-disambiguation "
        "question; empty otherwise.",
    )


__all__ = [
    "MessageSchema",
    "ConversationSchema",
    "ConversationCreateRequest",
    "ConversationCreateResponse",
    "ConversationListItem",
    "ChatRequest",
    "PlaceSchema",
    "DestinationCandidateSchema",
    "ChatResponse",
]
