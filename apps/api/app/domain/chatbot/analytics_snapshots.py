"""Analytics snapshot materialization for ChatBot Hub."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import Session, select

from app.domain.chatbot.models import (
    ChatbotAnalyticsSnapshot,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotMessage,
    ChatbotMessageSender,
    ChatbotOptOut,
    get_datetime_utc,
)


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _end_exclusive(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _channel_type(value: object) -> ChatbotChannelType:
    return value if isinstance(value, ChatbotChannelType) else ChatbotChannelType(str(value))


def _is_lead(conversation: ChatbotConversation) -> bool:
    return (
        _enum_value(conversation.outcome) == ChatbotConversationOutcome.lead_captured.value
        or conversation.shared_contact_id is not None
    )


def _is_escalated(conversation: ChatbotConversation) -> bool:
    return bool(
        conversation.escalated
        or _enum_value(conversation.outcome) == ChatbotConversationOutcome.escalated.value
    )


def _is_bot_resolved(conversation: ChatbotConversation) -> bool:
    if _is_escalated(conversation) or _is_lead(conversation):
        return False
    return _enum_value(conversation.outcome) == ChatbotConversationOutcome.bot_resolved.value


def refresh_chatbot_analytics_snapshots(
    session: Session,
    *,
    workspace_id: str,
    target_date: date | None = None,
) -> int:
    """Refresh per-channel chatbot analytics snapshots for one workspace date."""
    snapshot_date = target_date or get_datetime_utc().date()
    start_at = _start_of_day(snapshot_date)
    end_at = _end_exclusive(snapshot_date)

    conversations = list(
        session.exec(
            select(ChatbotConversation).where(
                ChatbotConversation.workspace_id == workspace_id,
                ChatbotConversation.deleted_at.is_(None),
                ChatbotConversation.last_message_at >= start_at,
                ChatbotConversation.last_message_at < end_at,
            )
        ).all()
    )
    conversation_channels = {conversation.id: _channel_type(conversation.channel_type) for conversation in conversations}
    channel_rows: dict[ChatbotChannelType, dict[str, int]] = defaultdict(
        lambda: {
            "total_conversations": 0,
            "bot_messages": 0,
            "escalations": 0,
            "leads_captured": 0,
            "bot_resolved": 0,
            "opt_outs": 0,
        }
    )

    for conversation in conversations:
        channel = channel_rows[_channel_type(conversation.channel_type)]
        channel["total_conversations"] += 1
        if _is_lead(conversation):
            channel["leads_captured"] += 1
        elif _is_escalated(conversation):
            channel["escalations"] += 1
        elif _is_bot_resolved(conversation):
            channel["bot_resolved"] += 1

    if conversation_channels:
        bot_messages = session.exec(
            select(ChatbotMessage.conversation_id).where(
                ChatbotMessage.workspace_id == workspace_id,
                ChatbotMessage.conversation_id.in_(list(conversation_channels.keys())),
                ChatbotMessage.deleted_at.is_(None),
                ChatbotMessage.sender == ChatbotMessageSender.bot,
                ChatbotMessage.created_at >= start_at,
                ChatbotMessage.created_at < end_at,
            )
        ).all()
        for conversation_id in bot_messages:
            channel_rows[conversation_channels[conversation_id]]["bot_messages"] += 1

    opt_outs = session.exec(
        select(ChatbotOptOut.channel_type).where(
            ChatbotOptOut.workspace_id == workspace_id,
            ChatbotOptOut.created_at >= start_at,
            ChatbotOptOut.created_at < end_at,
        )
    ).all()
    for channel_type in opt_outs:
        channel_rows[_channel_type(channel_type)]["opt_outs"] += 1

    existing_snapshots = session.exec(
        select(ChatbotAnalyticsSnapshot).where(
            ChatbotAnalyticsSnapshot.workspace_id == workspace_id,
            ChatbotAnalyticsSnapshot.snapshot_date == snapshot_date,
        )
    ).all()
    for snapshot in existing_snapshots:
        session.delete(snapshot)

    for channel_type, metrics in channel_rows.items():
        snapshot = ChatbotAnalyticsSnapshot(
            workspace_id=workspace_id,
            snapshot_date=snapshot_date,
            channel_type=channel_type,
        )
        snapshot.total_conversations = metrics["total_conversations"]
        snapshot.bot_messages = metrics["bot_messages"]
        snapshot.escalations = metrics["escalations"]
        snapshot.leads_captured = metrics["leads_captured"]
        snapshot.metrics_json = {
            "bot_resolved": metrics["bot_resolved"],
            "opt_outs": metrics["opt_outs"],
        }
        session.add(snapshot)

    session.flush()
    return len(channel_rows)


def refresh_all_chatbot_analytics_snapshots(
    session: Session,
    *,
    target_date: date | None = None,
) -> dict[str, int]:
    """Refresh chatbot analytics snapshots for every workspace active on a date."""
    snapshot_date = target_date or get_datetime_utc().date()
    start_at = _start_of_day(snapshot_date)
    end_at = _end_exclusive(snapshot_date)

    workspace_ids = {
        str(workspace_id)
        for workspace_id in session.exec(
            select(ChatbotConversation.workspace_id)
            .where(
                ChatbotConversation.deleted_at.is_(None),
                ChatbotConversation.last_message_at >= start_at,
                ChatbotConversation.last_message_at < end_at,
            )
            .distinct()
        ).all()
    }
    workspace_ids.update(
        str(workspace_id)
        for workspace_id in session.exec(
            select(ChatbotOptOut.workspace_id)
            .where(
                ChatbotOptOut.created_at >= start_at,
                ChatbotOptOut.created_at < end_at,
            )
            .distinct()
        ).all()
    )

    return {
        workspace_id: refresh_chatbot_analytics_snapshots(
            session,
            workspace_id=workspace_id,
            target_date=snapshot_date,
        )
        for workspace_id in sorted(workspace_ids)
    }
