"""ChatBot Hub analytics routes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotMessage,
    ChatbotMessageSender,
    ChatbotOptOut,
    get_datetime_utc,
)
from app.domain.chatbot.schemas import (
    ChatbotAnalyticsChannelBreakdownPublic,
    ChatbotAnalyticsConversionFunnelPublic,
    ChatbotAnalyticsPublic,
    ChatbotAnalyticsSeriesPointPublic,
    ChatbotAnalyticsTotalsPublic,
)
from app.domain.sequences.models import ContactSequenceState
from app.domain.voice.models import CallRequest
from app.domain_models import ContactProgression, ProspectingSnapshot
from app.models import User
from app.routers.chatbot.router import WorkspaceId, require_chatbot_agent

router = APIRouter(prefix="/analytics", tags=["chatbot-analytics"])


def _date_bounds(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    end = date_to or get_datetime_utc().date()
    start = date_from or (end - timedelta(days=6))
    if start > end:
        raise HTTPException(status_code=400, detail="from must be before or equal to to")
    return start, end


def _start_of_day(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _end_exclusive(value: date) -> datetime:
    return datetime.combine(value + timedelta(days=1), time.min, tzinfo=timezone.utc)


def _row_date(value: datetime | None) -> date:
    if value is None:
        return get_datetime_utc().date()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).date()


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _channel_type(value) -> ChatbotChannelType:
    return value if isinstance(value, ChatbotChannelType) else ChatbotChannelType(str(value))


def _is_lead(conversation: ChatbotConversation) -> bool:
    return _enum_value(conversation.outcome) == ChatbotConversationOutcome.lead_captured.value or conversation.contact_id is not None


def _is_escalated(conversation: ChatbotConversation) -> bool:
    return bool(conversation.escalated or _enum_value(conversation.outcome) == ChatbotConversationOutcome.escalated.value)


def _is_bot_resolved(conversation: ChatbotConversation) -> bool:
    if _is_escalated(conversation) or _is_lead(conversation):
        return False
    return _enum_value(conversation.outcome) == ChatbotConversationOutcome.bot_resolved.value or not conversation.escalated


def _distinct_contact_count(rows) -> int:
    return len({row for row in rows if row is not None})


def _conversion_funnel(
    *,
    session,
    workspace_id: str,
    conversations: list[ChatbotConversation],
    leads_captured: int,
) -> ChatbotAnalyticsConversionFunnelPublic:
    lead_contact_ids = {
        conversation.contact_id
        for conversation in conversations
        if _is_lead(conversation) and conversation.contact_id is not None
    }
    if not lead_contact_ids:
        return ChatbotAnalyticsConversionFunnelPublic(
            conversations=len(conversations),
            leads_captured=leads_captured,
            prospecting_researched=0,
            added_to_campaign=0,
            sequence_enrolled=0,
            voice_followups=0,
        )

    contact_ids = list(lead_contact_ids)
    researched = _distinct_contact_count(
        session.exec(
            select(ProspectingSnapshot.contact_id).where(
                ProspectingSnapshot.workspace_id == workspace_id,
                ProspectingSnapshot.contact_id.in_(contact_ids),
            )
        ).all()
    )
    added_to_campaign = _distinct_contact_count(
        session.exec(
            select(ContactProgression.contact_id).where(
                ContactProgression.contact_id.in_(contact_ids),
            )
        ).all()
    )
    sequence_enrolled = _distinct_contact_count(
        session.exec(
            select(ContactSequenceState.contact_id).where(
                ContactSequenceState.contact_id.in_(contact_ids),
            )
        ).all()
    )
    voice_followups = _distinct_contact_count(
        session.exec(
            select(CallRequest.contact_id).where(
                CallRequest.contact_id.in_(contact_ids),
            )
        ).all()
    )

    return ChatbotAnalyticsConversionFunnelPublic(
        conversations=len(conversations),
        leads_captured=leads_captured,
        prospecting_researched=researched,
        added_to_campaign=added_to_campaign,
        sequence_enrolled=sequence_enrolled,
        voice_followups=voice_followups,
    )


@router.get("", response_model=ChatbotAnalyticsPublic)
def get_chatbot_analytics(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> ChatbotAnalyticsPublic:
    """Return workspace-scoped chatbot analytics for the selected date range."""
    start, end = _date_bounds(date_from, date_to)
    start_at = _start_of_day(start)
    end_at = _end_exclusive(end)

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
    conversation_ids = [row.id for row in conversations]
    bot_message_count = 0
    if conversation_ids:
        bot_message_count = len(
            list(
                session.exec(
                    select(ChatbotMessage.id).where(
                        ChatbotMessage.workspace_id == workspace_id,
                        ChatbotMessage.conversation_id.in_(conversation_ids),
                        ChatbotMessage.deleted_at.is_(None),
                        ChatbotMessage.sender == ChatbotMessageSender.bot,
                    )
                ).all()
            )
        )

    opt_outs = list(
        session.exec(
            select(ChatbotOptOut).where(
                ChatbotOptOut.workspace_id == workspace_id,
                ChatbotOptOut.created_at >= start_at,
                ChatbotOptOut.created_at < end_at,
            )
        ).all()
    )

    series = {
        start + timedelta(days=offset): {
            "conversations": 0,
            "bot_messages": 0,
            "leads_captured": 0,
            "escalations": 0,
            "opt_outs": 0,
        }
        for offset in range((end - start).days + 1)
    }
    channel_rows: dict[ChatbotChannelType, dict[str, int]] = defaultdict(
        lambda: {
            "bot_resolved": 0,
            "escalated": 0,
            "lead_captured": 0,
            "opted_out": 0,
            "conversations": 0,
        }
    )

    leads = 0
    escalations = 0
    contained = 0
    for conversation in conversations:
        day = _row_date(conversation.last_message_at)
        channel_type = _channel_type(conversation.channel_type)
        channel = channel_rows[channel_type]
        channel["conversations"] += 1
        series[day]["conversations"] += 1

        if _is_lead(conversation):
            leads += 1
            channel["lead_captured"] += 1
            series[day]["leads_captured"] += 1
        elif _is_escalated(conversation):
            escalations += 1
            channel["escalated"] += 1
            series[day]["escalations"] += 1
        elif _is_bot_resolved(conversation):
            contained += 1
            channel["bot_resolved"] += 1

    bot_messages_by_day = defaultdict(int)
    if conversation_ids:
        bot_messages = session.exec(
            select(ChatbotMessage.created_at).where(
                ChatbotMessage.workspace_id == workspace_id,
                ChatbotMessage.conversation_id.in_(conversation_ids),
                ChatbotMessage.deleted_at.is_(None),
                ChatbotMessage.sender == ChatbotMessageSender.bot,
            )
        ).all()
        for created_at in bot_messages:
            bot_messages_by_day[_row_date(created_at)] += 1
    for day, count in bot_messages_by_day.items():
        if day in series:
            series[day]["bot_messages"] = count

    for opt_out in opt_outs:
        day = _row_date(opt_out.created_at)
        if day in series:
            series[day]["opt_outs"] += 1
        channel_rows[_channel_type(opt_out.channel_type)]["opted_out"] += 1

    total = len(conversations)
    containment_rate = round((contained / total) * 100, 1) if total else 0.0
    updated_candidates = [row.updated_at for row in conversations if row.updated_at]
    updated_at = max(updated_candidates) if updated_candidates else get_datetime_utc()

    return ChatbotAnalyticsPublic(
        workspace_id=workspace_id,
        date_from=start,
        date_to=end,
        updated_at=updated_at,
        totals=ChatbotAnalyticsTotalsPublic(
            conversations=total,
            containment_rate=containment_rate,
            leads_captured=leads,
            escalations=escalations,
            bot_messages=bot_message_count,
            opt_outs=len(opt_outs),
        ),
        conversion_funnel=_conversion_funnel(
            session=session,
            workspace_id=workspace_id,
            conversations=conversations,
            leads_captured=leads,
        ),
        timeseries=[
            ChatbotAnalyticsSeriesPointPublic(date=day, **values)
            for day, values in sorted(series.items(), key=lambda item: item[0])
        ],
        channel_breakdown=[
            ChatbotAnalyticsChannelBreakdownPublic(channel_type=channel, **values)
            for channel, values in sorted(channel_rows.items(), key=lambda item: item[0].value)
        ],
    )
