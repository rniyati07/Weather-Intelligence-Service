"""SQLAlchemy implementations of repository ports.

Translates between ORM rows and the plain domain records. No ORM instance
is ever returned across the port boundary — only `select()`, `.scalars()`,
and mapping happen here.
"""

from collections import defaultdict
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.conversation import Conversation, Message
from app.domain.entities.persistence import (
    DailyIntelligenceRecord,
    Location,
    RawWeatherReading,
    RiskLevel,
    TravelAdvisory,
)
from app.domain.ports.conversation import ConversationRepository
from app.domain.ports.repository import WeatherRepository
from app.infrastructure.persistence.models import (
    ConversationModel,
    LocationModel,
    MessageModel,
    WeatherIntelligenceDailyModel,
    WeatherReadingRawModel,
)


def _location_to_domain(row: LocationModel) -> Location:
    return Location(
        id=row.id,
        name=row.name,
        latitude=row.latitude,
        longitude=row.longitude,
        normalized_key=row.normalized_key,
    )


def _reading_to_domain(row: WeatherReadingRawModel) -> RawWeatherReading:
    return RawWeatherReading(
        id=row.id,
        location_id=row.location_id,
        provider=row.provider,
        fetched_at=row.fetched_at,
        valid_date=row.valid_date,
        raw_payload=row.raw_payload,
        normalized_payload=row.normalized_payload,
    )


def _intelligence_to_domain(row: WeatherIntelligenceDailyModel) -> DailyIntelligenceRecord:
    # risk_level/travel_advisory are DB-constrained (CHECK constraints in
    # models.py) to exactly these literals, so the cast is safe.
    return DailyIntelligenceRecord(
        id=row.id,
        location_id=row.location_id,
        date=row.date,
        risk_level=cast(RiskLevel, row.risk_level),
        risk_factors=row.risk_factors,
        activity_scores=row.activity_scores,
        packing=row.packing,
        travel_advisory=cast(TravelAdvisory, row.travel_advisory),
        rule_config_version=row.rule_config_version,
        generated_at=row.generated_at,
    )


class SqlAlchemyWeatherRepository(WeatherRepository):
    """`WeatherRepository` backed by SQLAlchemy async sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_location(
        self, *, name: str, latitude: float, longitude: float, normalized_key: str
    ) -> Location:
        stmt = select(LocationModel).where(LocationModel.normalized_key == normalized_key)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return _location_to_domain(existing)

        row = LocationModel(
            name=name, latitude=latitude, longitude=longitude, normalized_key=normalized_key
        )
        self._session.add(row)
        await self._session.flush()
        return _location_to_domain(row)

    async def save_raw_reading(self, reading: RawWeatherReading) -> RawWeatherReading:
        row = WeatherReadingRawModel(
            location_id=reading.location_id,
            provider=reading.provider,
            fetched_at=reading.fetched_at,
            valid_date=reading.valid_date,
            raw_payload=reading.raw_payload,
            normalized_payload=reading.normalized_payload,
        )
        self._session.add(row)
        await self._session.flush()
        return _reading_to_domain(row)

    async def get_raw_readings(
        self, *, location_id: int, start_date: date, end_date: date
    ) -> list[RawWeatherReading]:
        stmt = (
            select(WeatherReadingRawModel)
            .where(
                WeatherReadingRawModel.location_id == location_id,
                WeatherReadingRawModel.valid_date >= start_date,
                WeatherReadingRawModel.valid_date <= end_date,
            )
            .order_by(WeatherReadingRawModel.valid_date)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_reading_to_domain(row) for row in rows]

    async def save_intelligence(
        self, record: DailyIntelligenceRecord
    ) -> DailyIntelligenceRecord:
        row = WeatherIntelligenceDailyModel(
            location_id=record.location_id,
            date=record.date,
            risk_level=record.risk_level,
            risk_factors=record.risk_factors,
            activity_scores=record.activity_scores,
            packing=record.packing,
            travel_advisory=record.travel_advisory,
            rule_config_version=record.rule_config_version,
            generated_at=record.generated_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _intelligence_to_domain(row)

    async def get_fresh_intelligence(
        self,
        *,
        location_id: int,
        start_date: date,
        end_date: date,
        rule_config_version: str,
        fresh_since: datetime,
    ) -> list[DailyIntelligenceRecord]:
        stmt = (
            select(WeatherIntelligenceDailyModel)
            .where(
                WeatherIntelligenceDailyModel.location_id == location_id,
                WeatherIntelligenceDailyModel.date >= start_date,
                WeatherIntelligenceDailyModel.date <= end_date,
                WeatherIntelligenceDailyModel.rule_config_version == rule_config_version,
                WeatherIntelligenceDailyModel.generated_at >= fresh_since,
            )
            .order_by(WeatherIntelligenceDailyModel.date)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_intelligence_to_domain(row) for row in rows]


def _conversation_to_domain(row: ConversationModel, messages: list[MessageModel]) -> Conversation:
    """`messages` must be fetched separately (`_fetch_messages`) — `row` has
    no `.messages` attribute to read; see the model's docstring for why."""
    from app.domain.entities.trip import GeocodedPlace, TripContext, parse_iso_date

    tc_data = row.trip_context or {}
    dest = tc_data.get("destination")
    destination = (
        GeocodedPlace(
            name=dest["name"],
            latitude=dest["latitude"],
            longitude=dest["longitude"],
            country=dest.get("country"),
            country_code=dest.get("country_code"),
            admin1=dest.get("admin1"),
            timezone=dest.get("timezone"),
        )
        if dest
        else None
    )

    # Stored as `.isoformat()` strings (JSONB has no native date type) — must
    # go back through `parse_iso_date`, not assigned raw, or every date-typed
    # field on `TripContext` silently becomes a `str` on the very next read.
    trip_context = TripContext(
        destination=destination,
        destination_query=tc_data.get("destination_query"),
        start_date=parse_iso_date(tc_data.get("start_date")),
        end_date=parse_iso_date(tc_data.get("end_date")),
        interests=tuple(tc_data.get("interests", [])),
        travel_style=tc_data.get("travel_style"),
        pace=tc_data.get("pace"),
    )

    messages_domain = tuple(
        Message(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            metadata=msg.message_metadata,
            created_at=msg.created_at,
        )
        for msg in messages
    )

    return Conversation(
        id=row.id,
        trip_context=trip_context,
        messages=messages_domain,
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_active=row.is_active,
    )


def _conversation_to_model(conversation: Conversation) -> ConversationModel:
    tc = conversation.trip_context
    dest_dict = None
    if tc.destination:
        dest_dict = {
            "name": tc.destination.name,
            "latitude": tc.destination.latitude,
            "longitude": tc.destination.longitude,
            "country": tc.destination.country,
            "country_code": tc.destination.country_code,
            "admin1": tc.destination.admin1,
            "timezone": tc.destination.timezone,
        }

    trip_context = {
        "destination": dest_dict,
        "destination_query": tc.destination_query,
        "start_date": tc.start_date.isoformat() if tc.start_date else None,
        "end_date": tc.end_date.isoformat() if tc.end_date else None,
        "interests": list(tc.interests),
        "travel_style": tc.travel_style,
        "pace": tc.pace,
    }

    return ConversationModel(
        id=conversation.id,
        trip_context=trip_context,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        is_active=conversation.is_active,
    )


def _message_to_model(message: Message) -> MessageModel:
    return MessageModel(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        message_metadata=message.metadata,
        created_at=message.created_at,
    )


class SqlAlchemyConversationRepository(ConversationRepository):
    """`ConversationRepository` backed by SQLAlchemy async sessions.

    Every method that needs a conversation's messages fetches them with an
    explicit `select()` (`_fetch_messages`/`_fetch_messages_by_conversation`)
    rather than reading an ORM relationship — see `ConversationModel`'s
    docstring for why the relationship doesn't exist. This is not a
    workaround; it is the same pattern `SqlAlchemyWeatherRepository` already
    uses for every other child table in this file.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _fetch_messages(self, conversation_id: UUID) -> list[MessageModel]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get(self, conversation_id: UUID) -> Conversation | None:
        stmt = select(ConversationModel).where(ConversationModel.id == conversation_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        messages = await self._fetch_messages(conversation_id)
        return _conversation_to_domain(row, messages)

    async def save(self, conversation: Conversation) -> Conversation:
        existing = await self._session.get(ConversationModel, conversation.id)
        if existing is None:
            model = _conversation_to_model(conversation)
            self._session.add(model)
            existing_msg_ids: set[UUID] = set()
        else:
            # Update fields that can change
            tc = conversation.trip_context
            dest_dict = None
            if tc.destination:
                dest_dict = {
                    "name": tc.destination.name,
                    "latitude": tc.destination.latitude,
                    "longitude": tc.destination.longitude,
                    "country": tc.destination.country,
                    "country_code": tc.destination.country_code,
                    "admin1": tc.destination.admin1,
                    "timezone": tc.destination.timezone,
                }
            existing.trip_context = {
                "destination": dest_dict,
                "destination_query": tc.destination_query,
                "start_date": tc.start_date.isoformat() if tc.start_date else None,
                "end_date": tc.end_date.isoformat() if tc.end_date else None,
                "interests": list(tc.interests),
                "travel_style": tc.travel_style,
                "pace": tc.pace,
            }
            existing.updated_at = conversation.updated_at
            existing.is_active = conversation.is_active

            id_stmt = select(MessageModel.id).where(
                MessageModel.conversation_id == conversation.id
            )
            existing_msg_ids = set((await self._session.execute(id_stmt)).scalars().all())

        # Sync messages: add new ones
        for msg in conversation.messages:
            if msg.id not in existing_msg_ids:
                self._session.add(_message_to_model(msg))

        await self._session.flush()
        return conversation

    async def get_active_for_user(self, user_id: str | None = None) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(ConversationModel.is_active.is_(True))
            .order_by(desc(ConversationModel.updated_at))
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        if not rows:
            return []

        # One extra query for every conversation's messages, batched by id,
        # rather than N+1 — the only place this repository fetches more than
        # one conversation's messages at once.
        conversation_ids = [row.id for row in rows]
        messages_stmt = (
            select(MessageModel)
            .where(MessageModel.conversation_id.in_(conversation_ids))
            .order_by(MessageModel.created_at)
        )
        all_messages = (await self._session.execute(messages_stmt)).scalars().all()
        messages_by_conversation: dict[UUID, list[MessageModel]] = defaultdict(list)
        for message_row in all_messages:
            messages_by_conversation[message_row.conversation_id].append(message_row)

        return [
            _conversation_to_domain(row, messages_by_conversation.get(row.id, []))
            for row in rows
        ]

    async def get_messages(
        self,
        conversation_id: UUID,
        *,
        limit: int | None = None,
        offset: int = 0,
        before: datetime | None = None,
    ) -> list[Message]:
        stmt = select(MessageModel).where(MessageModel.conversation_id == conversation_id)
        if before:
            stmt = stmt.where(MessageModel.created_at < before)
        stmt = stmt.order_by(desc(MessageModel.created_at)).offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            Message(
                id=row.id,
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                metadata=row.message_metadata,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def delete(self, conversation_id: UUID) -> bool:
        row = await self._session.get(ConversationModel, conversation_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True
