"""Conversation and Message — the persistent aggregate for chat.

`Conversation` owns a `TripContext` and an append-only message log.
`Message` is one turn: user or assistant content plus optional metadata.
All frozen per guide §3.2 — no mutation across turns.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities.trip import TripContext


@dataclass(frozen=True, slots=True)
class Message:
    """One message in a conversation.

    `role` is `"user"` or `"assistant"`. `content` is the visible text.
    `metadata` carries structured extras the orchestrator may attach
    (e.g. extracted entities, intelligence summary, tool calls) without
    polluting the conversation text itself.
    """

    id: UUID
    conversation_id: UUID
    role: str
    content: str
    metadata: dict[str, object]
    created_at: datetime

    @staticmethod
    def user(
        conversation_id: UUID, content: str, metadata: dict[str, object] | None = None
    ) -> "Message":
        return Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )

    @staticmethod
    def assistant(
        conversation_id: UUID,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> "Message":
        return Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            metadata=metadata or {},
            created_at=datetime.now(UTC),
        )


@dataclass(frozen=True, slots=True)
class Conversation:
    """A conversation aggregate: context + message log.

    The `TripContext` is the single source of truth for what the user
    has told us. Messages are the audit trail. Both are append-only:
    new state = new `Conversation` with updated context + appended message.
    """

    id: UUID
    trip_context: TripContext
    messages: tuple[Message, ...]
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    @staticmethod
    def start() -> "Conversation":
        """Create a brand-new empty conversation."""
        now = datetime.now(UTC)
        return Conversation(
            id=uuid4(),
            trip_context=TripContext(),
            messages=(),
            created_at=now,
            updated_at=now,
            is_active=True,
        )

    def add_user_message(
        self, content: str, metadata: dict[str, object] | None = None
    ) -> "Conversation":
        """Append a user message; context unchanged (extraction happens separately)."""
        msg = Message.user(self.id, content, metadata)
        return self._with_message(msg)

    def add_assistant_message(
        self, content: str, metadata: dict[str, object] | None = None
    ) -> "Conversation":
        """Append an assistant message."""
        msg = Message.assistant(self.id, content, metadata)
        return self._with_message(msg)

    def update_context(self, new_context: TripContext) -> "Conversation":
        """Return a new conversation with an updated trip context."""
        return replace(self, trip_context=new_context, updated_at=datetime.now(UTC))

    def archive(self) -> "Conversation":
        return replace(self, is_active=False, updated_at=datetime.now(UTC))

    def _with_message(self, msg: Message) -> "Conversation":
        return replace(
            self,
            messages=(*self.messages, msg),
            updated_at=msg.created_at,
        )

    @property
    def last_user_message(self) -> Message | None:
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

    @property
    def last_assistant_message(self) -> Message | None:
        for msg in reversed(self.messages):
            if msg.role == "assistant":
                return msg
        return None


__all__ = ["Conversation", "Message"]