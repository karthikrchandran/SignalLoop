"""Conversation retention purge helpers for ChatBot Hub."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotConversation,
    ChatbotMessage,
)

MIN_RETENTION_DAYS = 30
DEFAULT_RETENTION_DAYS = 90


@dataclass(frozen=True)
class RetentionPurgeResult:
    """Retention purge summary."""

    workspace_id: str
    cutoff_at: datetime
    conversations_purged: int
    messages_purged: int


def normalized_retention_days(value: int | None) -> int:
    """Validate retention days."""
    days = value or DEFAULT_RETENTION_DAYS
    if days < MIN_RETENTION_DAYS:
        raise ValueError("Retention cannot be below 30 days")
    return days


def purge_workspace_conversations(
    session: Session,
    *,
    workspace_id: str,
    now: datetime | None = None,
) -> RetentionPurgeResult:
    """Soft-delete conversations/messages older than the workspace retention window."""
    current = now or datetime.now(timezone.utc)
    config = session.exec(
        select(ChatbotBotConfig).where(ChatbotBotConfig.workspace_id == workspace_id)
    ).first()
    retention_days = normalized_retention_days(config.retention_days if config else DEFAULT_RETENTION_DAYS)
    cutoff = current - timedelta(days=retention_days)

    conversations = list(
        session.exec(
            select(ChatbotConversation).where(
                ChatbotConversation.workspace_id == workspace_id,
                ChatbotConversation.deleted_at.is_(None),
                ChatbotConversation.last_message_at < cutoff,
            )
        ).all()
    )
    conversation_ids = [row.id for row in conversations]
    messages = []
    if conversation_ids:
        messages = list(
            session.exec(
                select(ChatbotMessage).where(
                    ChatbotMessage.workspace_id == workspace_id,
                    ChatbotMessage.deleted_at.is_(None),
                    ChatbotMessage.conversation_id.in_(conversation_ids),
                )
            ).all()
        )

    for row in conversations:
        row.deleted_at = current
        session.add(row)
    for row in messages:
        row.deleted_at = current
        session.add(row)

    result = RetentionPurgeResult(
        workspace_id=workspace_id,
        cutoff_at=cutoff,
        conversations_purged=len(conversations),
        messages_purged=len(messages),
    )
    append_audit_event_to_session(
        session,
        event_name="chatbot_retention_purged",
        workspace_id=workspace_id,
        actor_role="system",
        resource_type="chatbot_retention",
        resource_id=workspace_id,
        payload={
            "cutoff_at": cutoff.isoformat(),
            "conversations_purged": result.conversations_purged,
            "messages_purged": result.messages_purged,
        },
    )
    return result

