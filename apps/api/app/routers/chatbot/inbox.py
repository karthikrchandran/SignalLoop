"""ChatBot Hub inbox and human handoff routes."""

from __future__ import annotations

import base64
import csv
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.chatbot.engine import publish_inbox_event
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
    ChatbotOptOut,
    get_datetime_utc,
)
from app.domain.chatbot.repositories import get_conversation_by_id
from app.domain.chatbot.schemas import (
    ChatbotLeadDetails,
    ChatbotThreadActionPublic,
    ChatbotThreadDetailPublic,
    ChatbotThreadMessagePublic,
    ChatbotThreadReplyRequest,
    ChatbotThreadsPublic,
    ChatbotThreadSummary,
)
from app.domain_models import Contact
from app.infrastructure.providers.chat.registry import build_chat_adapter
from app.infrastructure.providers.chat.whatsapp_cloud import WhatsAppWindowExpiredError
from app.models import User
from app.routers.chatbot.router import (
    WorkspaceId,
    require_chatbot_admin,
    require_chatbot_agent,
)

router = APIRouter(prefix="/inbox", tags=["chatbot-inbox"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _cursor(row: ChatbotConversation) -> str:
    timestamp = row.last_message_at or row.created_at
    raw = f"{_to_utc(timestamp).isoformat()}|{row.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        timestamp_raw, row_id = raw.split("|", 1)
        return _to_utc(datetime.fromisoformat(timestamp_raw)), uuid.UUID(row_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


def _is_window_open(conversation: ChatbotConversation, now: datetime | None = None) -> bool:
    if conversation.channel_type != ChatbotChannelType.whatsapp_business:
        return True
    if conversation.customer_last_message_at is None:
        return False
    return (_to_utc(now or _now()) - _to_utc(conversation.customer_last_message_at)) <= timedelta(hours=24)


def _opt_out(session: Session, conversation: ChatbotConversation) -> ChatbotOptOut | None:
    return session.exec(
        select(ChatbotOptOut).where(
            ChatbotOptOut.workspace_id == conversation.workspace_id,
            ChatbotOptOut.channel_type == conversation.channel_type,
            ChatbotOptOut.visitor_id == conversation.visitor_id,
            ChatbotOptOut.reopt_in_invited_at.is_(None),
        )
    ).first()


def _lead_details(session: Session, conversation: ChatbotConversation) -> ChatbotLeadDetails | None:
    if not conversation.contact_id:
        return None
    contact = session.exec(
        select(Contact).where(
            Contact.workspace_id == conversation.workspace_id,
            Contact.id == conversation.contact_id,
        )
    ).first()
    if not contact:
        return None
    name = " ".join(part for part in [contact.first_name, contact.last_name] if part) or None
    return ChatbotLeadDetails(
        contact_id=contact.id,
        name=name,
        email=contact.email,
        phone=contact.phone,
        source_channel=contact.source_channel,
        tags=list(contact.tags_json or []),
        intents=list(contact.intent_json or []),
    )


def _last_message(session: Session, conversation: ChatbotConversation) -> ChatbotMessage | None:
    return session.exec(
        select(ChatbotMessage)
        .where(
            ChatbotMessage.workspace_id == conversation.workspace_id,
            ChatbotMessage.conversation_id == conversation.id,
            ChatbotMessage.deleted_at.is_(None),
        )
        .order_by(col(ChatbotMessage.created_at).desc())
    ).first()


def _summary(session: Session, conversation: ChatbotConversation) -> ChatbotThreadSummary:
    last_message = _last_message(session, conversation)
    opted_out = _opt_out(session, conversation) is not None
    return ChatbotThreadSummary(
        id=conversation.id,
        workspace_id=conversation.workspace_id,
        channel_type=conversation.channel_type,
        visitor_id=conversation.visitor_id,
        status=conversation.status,
        outcome=conversation.outcome,
        preview=last_message.content if last_message else None,
        last_message_at=conversation.last_message_at,
        customer_last_message_at=conversation.customer_last_message_at,
        is_whatsapp_window_open=_is_window_open(conversation),
        is_opted_out=opted_out,
        escalation_reason=conversation.escalation_reason,
        lead=_lead_details(session, conversation),
    )


def _message_public(row: ChatbotMessage) -> ChatbotThreadMessagePublic:
    return ChatbotThreadMessagePublic(
        id=row.id,
        direction=row.direction,
        sender=row.sender,
        message_type=row.message_type,
        content=row.content,
        bot_confidence=row.bot_confidence,
        metadata_json=row.metadata_json,
        created_at=row.created_at,
        delivered_at=row.delivered_at,
    )


def _detail(session: Session, conversation: ChatbotConversation) -> ChatbotThreadDetailPublic:
    summary = _summary(session, conversation)
    messages = list(
        session.exec(
            select(ChatbotMessage)
            .where(
                ChatbotMessage.workspace_id == conversation.workspace_id,
                ChatbotMessage.conversation_id == conversation.id,
                ChatbotMessage.deleted_at.is_(None),
            )
            .order_by(ChatbotMessage.created_at)
        ).all()
    )
    return ChatbotThreadDetailPublic(**summary.model_dump(), messages=[_message_public(row) for row in messages])


def _filtered_threads(
    session: Session,
    *,
    workspace_id: str,
    channel_type: ChatbotChannelType | None,
    status_filter: ChatbotConversationStatus | None,
    date_from: datetime | None,
    date_to: datetime | None,
    cursor: str | None,
    limit: int,
) -> tuple[list[ChatbotConversation], str | None]:
    stmt = select(ChatbotConversation).where(
        ChatbotConversation.workspace_id == workspace_id,
        ChatbotConversation.deleted_at.is_(None),
    )
    if channel_type:
        stmt = stmt.where(ChatbotConversation.channel_type == channel_type)
    if status_filter:
        stmt = stmt.where(ChatbotConversation.status == status_filter)
    if date_from:
        stmt = stmt.where(ChatbotConversation.last_message_at >= date_from)
    if date_to:
        stmt = stmt.where(ChatbotConversation.last_message_at <= date_to)
    decoded_cursor = _decode_cursor(cursor)
    if decoded_cursor:
        cursor_time, cursor_id = decoded_cursor
        stmt = stmt.where(
            (ChatbotConversation.last_message_at < cursor_time)
            | (
                (ChatbotConversation.last_message_at == cursor_time)
                & (ChatbotConversation.id < cursor_id)
            )
        )
    rows = list(
        session.exec(
            stmt.order_by(
                col(ChatbotConversation.last_message_at).desc(),
                col(ChatbotConversation.id).desc(),
            ).limit(limit + 1)
        ).all()
    )
    next_cursor = _cursor(rows[-1]) if len(rows) > limit else None
    return rows[:limit], next_cursor


@router.get("/threads", response_model=ChatbotThreadsPublic)
def list_threads(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
    channel_type: Annotated[ChatbotChannelType | None, Query()] = None,
    status_filter: Annotated[ChatbotConversationStatus | None, Query(alias="status")] = None,
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> ChatbotThreadsPublic:
    """Return cursor-paginated inbox threads."""
    rows, next_cursor = _filtered_threads(
        session,
        workspace_id=workspace_id,
        channel_type=channel_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        cursor=cursor,
        limit=limit,
    )
    return ChatbotThreadsPublic(
        data=[_summary(session, row) for row in rows],
        count=len(rows),
        next_cursor=next_cursor,
    )


@router.get("/threads/{thread_id:uuid}", response_model=ChatbotThreadDetailPublic)
def get_thread(
    thread_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotThreadDetailPublic:
    """Return ordered message history for one thread."""
    conversation = get_conversation_by_id(workspace_id, session, thread_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Thread not found")
    return _detail(session, conversation)


@router.post("/threads/{thread_id:uuid}/reply", response_model=ChatbotThreadActionPublic)
async def reply_to_thread(
    thread_id: uuid.UUID,
    body: ChatbotThreadReplyRequest,
    request: Request,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotThreadActionPublic:
    """Append and dispatch an agent reply through the originating channel."""
    conversation = get_conversation_by_id(workspace_id, session, thread_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Thread not found")
    if conversation.channel_type == ChatbotChannelType.whatsapp_business and not _is_window_open(conversation):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="whatsapp_window_expired")

    try:
        adapter = build_chat_adapter(conversation.channel_type)
        receipt = await adapter.send_message(
            conversation.visitor_id,
            body.message,
            customer_last_message_at=conversation.customer_last_message_at,
        )
    except WhatsAppWindowExpiredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="whatsapp_window_expired")
    except KeyError:
        raise HTTPException(status_code=400, detail="No outbound adapter for this channel")

    now = get_datetime_utc()
    conversation.status = ChatbotConversationStatus.agent_active
    conversation.last_message_at = now
    conversation.updated_at = now
    conversation.resolved_at = None
    session.add(conversation)
    message = ChatbotMessage(
        workspace_id=workspace_id,
        conversation_id=conversation.id,
        provider_message_id=receipt.provider_message_id,
        direction=ChatbotMessageDirection.outbound,
        sender=ChatbotMessageSender.agent,
        content=body.message,
        metadata_json={"agent_id": str(current_user.id), "delivery_status": receipt.status},
        delivered_at=now if receipt.accepted else None,
    )
    session.add(message)
    append_audit_event_to_session(
        session,
        event_name="chatbot_agent_replied",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_conversation",
        resource_id=str(conversation.id),
        payload={"message_id": str(message.id), "channel_type": _enum_value(conversation.channel_type)},
    )
    redis = getattr(getattr(request.app.state, "redis_manager", None), "client", None)
    await publish_inbox_event(
        redis,
        workspace_id=workspace_id,
        event_type="message_appended",
        conversation=conversation,
        payload={"sender": "agent"},
    )
    session.commit()
    session.refresh(conversation)
    return ChatbotThreadActionPublic(thread=_detail(session, conversation))


@router.patch("/threads/{thread_id:uuid}/resolve", response_model=ChatbotThreadActionPublic)
async def resolve_thread(
    thread_id: uuid.UUID,
    request: Request,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotThreadActionPublic:
    """Mark a thread resolved."""
    conversation = get_conversation_by_id(workspace_id, session, thread_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Thread not found")
    conversation.status = ChatbotConversationStatus.resolved
    conversation.escalated = False
    conversation.resolved_at = get_datetime_utc()
    conversation.updated_at = conversation.resolved_at
    session.add(conversation)
    append_audit_event_to_session(
        session,
        event_name="chatbot_thread_resolved",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_conversation",
        resource_id=str(conversation.id),
    )
    redis = getattr(getattr(request.app.state, "redis_manager", None), "client", None)
    await publish_inbox_event(redis, workspace_id=workspace_id, event_type="status_changed", conversation=conversation)
    session.commit()
    session.refresh(conversation)
    return ChatbotThreadActionPublic(thread=_detail(session, conversation))


@router.patch("/threads/{thread_id:uuid}/reopen", response_model=ChatbotThreadActionPublic)
async def reopen_thread(
    thread_id: uuid.UUID,
    request: Request,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotThreadActionPublic:
    """Reopen a resolved thread."""
    conversation = get_conversation_by_id(workspace_id, session, thread_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Thread not found")
    conversation.status = ChatbotConversationStatus.escalated
    conversation.escalated = True
    conversation.resolved_at = None
    conversation.updated_at = get_datetime_utc()
    session.add(conversation)
    append_audit_event_to_session(
        session,
        event_name="chatbot_thread_reopened",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_conversation",
        resource_id=str(conversation.id),
    )
    redis = getattr(getattr(request.app.state, "redis_manager", None), "client", None)
    await publish_inbox_event(redis, workspace_id=workspace_id, event_type="status_changed", conversation=conversation)
    session.commit()
    session.refresh(conversation)
    return ChatbotThreadActionPublic(thread=_detail(session, conversation))


@router.get("/threads/export")
def export_threads(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
    format: Annotated[Literal["csv", "json"], Query()] = "csv",
    channel_type: Annotated[ChatbotChannelType | None, Query()] = None,
    date_from: Annotated[datetime | None, Query(alias="from")] = None,
    date_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> Response:
    """Export workspace-scoped conversation messages."""
    rows, _ = _filtered_threads(
        session,
        workspace_id=workspace_id,
        channel_type=channel_type,
        status_filter=None,
        date_from=date_from,
        date_to=date_to,
        cursor=None,
        limit=1000,
    )
    records: list[dict[str, object]] = []
    for conversation in rows:
        lead = _lead_details(session, conversation)
        messages = list(
            session.exec(
                select(ChatbotMessage)
                .where(
                    ChatbotMessage.workspace_id == workspace_id,
                    ChatbotMessage.conversation_id == conversation.id,
                    ChatbotMessage.deleted_at.is_(None),
                )
                .order_by(ChatbotMessage.created_at)
            ).all()
        )
        for message in messages:
            records.append(
                {
                    "message_id": str(message.id),
                    "conversation_id": str(conversation.id),
                    "channel": _enum_value(conversation.channel_type),
                    "visitor_id": conversation.visitor_id,
                    "sender_role": _enum_value(message.sender),
                    "message_text": message.content or "",
                    "sent_at": message.created_at.isoformat(),
                    "bot_confidence": message.bot_confidence,
                    "captured_lead_details": lead.model_dump(mode="json") if lead else {},
                }
            )

    if format == "json":
        return Response(
            content=json.dumps(records, default=str),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=chatbot-conversations.json"},
        )

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(records[0].keys()) if records else [
        "message_id",
        "conversation_id",
        "channel",
        "visitor_id",
        "sender_role",
        "message_text",
        "sent_at",
        "bot_confidence",
        "captured_lead_details",
    ])
    writer.writeheader()
    writer.writerows(records)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chatbot-conversations.csv"},
    )


@router.get("/events")
async def inbox_events(
    request: Request,
    workspace_id: WorkspaceId,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> StreamingResponse:
    """Stream inbox events through SSE."""

    async def event_stream() -> AsyncGenerator[str, None]:
        redis = getattr(getattr(request.app.state, "redis_manager", None), "client", None)
        if redis is None:
            yield "event: heartbeat\ndata: {}\n\n"
            return
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"chatbot:inbox:{workspace_id}:events")
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                yield f"event: inbox\ndata: {data}\n\n"
        finally:
            await pubsub.unsubscribe(f"chatbot:inbox:{workspace_id}:events")
            await pubsub.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
