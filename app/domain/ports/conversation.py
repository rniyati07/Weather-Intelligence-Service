"""ConversationRepository port: persistence contract for conversations and messages.

Implemented by infrastructure.persistence.repositories. Only the domain
entities in domain.entities.conversation cross this boundary.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.conversation import Conversation, Message


class ConversationRepository(ABC):
    """Persists conversations and their message logs."""

    @abstractmethod
    async def get(self, conversation_id: UUID) -> Conversation | None:
        """Return the conversation with all messages, or None if not found."""

    @abstractmethod
    async def save(self, conversation: Conversation) -> Conversation:
        """Persist a new or updated conversation. Returns the saved instance."""

    @abstractmethod
    async def get_active_for_user(self, user_id: str | None = None) -> list[Conversation]:
        """Return active conversations (for future multi-user support)."""

    @abstractmethod
    async def get_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
        before: datetime | None = None,
    ) -> list[Message]:
        """Return messages for a conversation with pagination support.

        If `before` is given, return messages created before that timestamp.
        Results are ordered newest-first for pagination, but callers should
        reverse for chronological display.
        """

    @abstractmethod
    async def delete(self, conversation_id: UUID) -> bool:
        """Delete a conversation and all its messages. Returns True if existed."""