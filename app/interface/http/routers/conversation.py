"""Conversation and Chat endpoints — conversational AI travel assistant.

Primary interface for the new conversational experience.
"""

from collections.abc import Sequence
from uuid import UUID

from fastapi import APIRouter, status

from app.domain.entities.conversation import Conversation, Message
from app.domain.entities.trip import TripContext
from app.interface.http.dependencies import (
    ApiKeyDep,
    ChatOrchestratorDep,
    ConversationRepositoryDep,
    RateLimitDep,
    RequestIdDep,
)
from app.interface.http.envelope import success_envelope
from app.interface.http.errors import NotFoundError, ValidationFailedError
from app.interface.http.schemas.common import ErrorDetailSchema, ResponseEnvelope
from app.interface.http.schemas.conversation import (
    ChatRequest,
    ChatResponse,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationListItem,
    ConversationSchema,
    DestinationCandidateSchema,
    MessageSchema,
    PlaceSchema,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


_ERROR_RESPONSES: dict[int | str, dict[str, str]] = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid API key."},
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Per-key rate limit exceeded."},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Service temporarily unavailable."},
}


def _messages_to_schemas(messages: Sequence[Message]) -> list[MessageSchema]:
    """Convert domain messages to MessageSchema."""
    return [
        MessageSchema(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            metadata=msg.metadata,
            created_at=msg.created_at,
        )
        for msg in messages
    ]


def _trip_context_to_dict(context: TripContext) -> dict[str, object]:
    """Convert TripContext to a JSON-serializable dict, camelCase throughout.

    `tripContext` is typed `dict[str, Any]` on the wire (API Spec: an open
    object, not a fixed schema), so it never passed through `CamelModel`'s
    alias generator the way every other field on this response does — this
    function is that boundary instead, and must keep pace with it by hand.
    A prior version emitted snake_case keys here (`destination_query`,
    `display_name`, ...), silently inconsistent with `conversationId`/
    `contextComplete`/`llmGenerated` on the same response and with every
    other endpoint in the API, which is a real, load-bearing bug for a
    frontend reading `tripContext.destination.displayName`.
    """
    result: dict[str, object] = {}
    if context.destination:
        result["destination"] = {
            "name": context.destination.name,
            "displayName": context.destination.display_name,
            "latitude": context.destination.latitude,
            "longitude": context.destination.longitude,
            "country": context.destination.country,
            "countryCode": context.destination.country_code,
            "admin1": context.destination.admin1,
            "timezone": context.destination.timezone,
        }
    if context.destination_query:
        result["destinationQuery"] = context.destination_query
    if context.start_date:
        result["startDate"] = context.start_date.isoformat()
    if context.end_date:
        result["endDate"] = context.end_date.isoformat()
    if context.interests:
        result["interests"] = list(context.interests)
    if context.travel_style:
        result["travelStyle"] = context.travel_style
    if context.pace:
        result["pace"] = context.pace
    return result


@router.post(
    "",
    response_model=ResponseEnvelope[ConversationCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    description="Start a new conversation. Optionally include an initial message.",
    responses=_ERROR_RESPONSES,
)
async def create_conversation(
    body: ConversationCreateRequest,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
    conversation_repo: ConversationRepositoryDep,
) -> ResponseEnvelope[ConversationCreateResponse]:
    """Create a new conversation."""
    conversation = Conversation.start()
    if body.initial_message:
        conversation = conversation.add_user_message(body.initial_message)

    conversation = await conversation_repo.save(conversation)

    schema = ConversationSchema(
        id=conversation.id,
        trip_context=_trip_context_to_dict(conversation.trip_context),
        messages=_messages_to_schemas(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_active=conversation.is_active,
    )

    return success_envelope(
        ConversationCreateResponse(conversation=schema),
        request_id=request_id,
    )


@router.get(
    "",
    response_model=ResponseEnvelope[list[ConversationListItem]],
    summary="List conversations",
    description="List all active conversations (for future multi-user support).",
    responses=_ERROR_RESPONSES,
)
async def list_conversations(
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
    conversation_repo: ConversationRepositoryDep,
) -> ResponseEnvelope[list[ConversationListItem]]:
    """List active conversations. `user_id` filtering is not yet wired —
    `get_active_for_user` accepts it for forward compatibility, but every
    caller today shares one API key with no per-user identity, so every
    active conversation is returned regardless of who is asking."""
    conversations = await conversation_repo.get_active_for_user()

    items = [
        ConversationListItem(
            id=conversation.id,
            trip_context=_trip_context_to_dict(conversation.trip_context),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            is_active=conversation.is_active,
            message_count=len(conversation.messages),
            last_message_preview=_preview(conversation.last_assistant_message),
        )
        for conversation in conversations
    ]

    return success_envelope(items, request_id=request_id)


_PREVIEW_MAX_LENGTH = 140


def _preview(message: Message | None) -> str | None:
    if message is None:
        return None
    text = message.content.strip()
    if len(text) <= _PREVIEW_MAX_LENGTH:
        return text
    return text[:_PREVIEW_MAX_LENGTH].rstrip() + "…"


@router.get(
    "/{conversation_id}",
    response_model=ResponseEnvelope[ConversationSchema],
    summary="Get conversation",
    description="Get a conversation with full message history.",
    responses={
        **_ERROR_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"description": "Conversation not found."},
    },
)
async def get_conversation(
    conversation_id: str,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
    conversation_repo: ConversationRepositoryDep,
) -> ResponseEnvelope[ConversationSchema]:
    """Get a conversation by ID."""
    try:
        conv_id = UUID(conversation_id)
    except ValueError:
        raise ValidationFailedError(
            "Invalid conversation ID format.",
            details=[ErrorDetailSchema(field="conversation_id", issue="must be a valid UUID")],
        ) from None

    conversation = await conversation_repo.get(conv_id)
    if conversation is None:
        raise NotFoundError("Conversation", conversation_id)

    schema = ConversationSchema(
        id=conversation.id,
        trip_context=_trip_context_to_dict(conversation.trip_context),
        messages=_messages_to_schemas(conversation.messages),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_active=conversation.is_active,
    )

    return success_envelope(schema, request_id=request_id)


@router.post(
    "/chat",
    response_model=ResponseEnvelope[ChatResponse],
    summary="Send a chat message",
    description=(
        "Send a message to the conversational travel assistant. "
        "If conversation_id is provided, continues that conversation. "
        "Otherwise starts a new one. Returns the assistant's response "
        "and updated trip context."
    ),
    responses={
        **_ERROR_RESPONSES,
        status.HTTP_404_NOT_FOUND: {"description": "Conversation not found."},
    },
)
async def chat(
    body: ChatRequest,
    request_id: RequestIdDep,
    _api_key: ApiKeyDep,
    _rate_limit: RateLimitDep,
    orchestrator: ChatOrchestratorDep,
) -> ResponseEnvelope[ChatResponse]:
    """Process a chat message and return the assistant response."""
    try:
        result = await orchestrator.process_message(
            conversation_id=body.conversation_id,
            user_message=body.message,
        )
    except ValueError as exc:
        if "not found" in str(exc).lower():
            raise NotFoundError("Conversation", str(body.conversation_id)) from exc
        raise

    response = ChatResponse(
        conversation_id=result.conversation.id,
        response=result.response,
        context_complete=result.context_complete,
        missing_essentials=list(result.missing_essentials),
        trip_context=_trip_context_to_dict(result.conversation.trip_context),
        intent=result.intent.value,
        llm_generated=result.llm_generated,
        places=[PlaceSchema.from_domain(place) for place in result.places],
        destination_candidates=[
            DestinationCandidateSchema.from_domain(candidate)
            for candidate in result.destination_candidates
        ],
    )

    return success_envelope(response, request_id=request_id)


__all__ = ["router"]