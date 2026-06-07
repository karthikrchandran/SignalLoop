"""Workspace-scoped repository helpers for ChatBot Hub."""

from __future__ import annotations

from sqlmodel import Session, col, func, select

from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotChannelConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeSource,
    ChatbotMessage,
    ChatbotOptOut,
)


def get_channel_config_by_id(
    workspace_id: str,
    session: Session,
    channel_id: object,
) -> ChatbotChannelConfig | None:
    """Return one workspace-scoped channel config by id."""
    return session.exec(
        select(ChatbotChannelConfig).where(
            ChatbotChannelConfig.workspace_id == workspace_id,
            ChatbotChannelConfig.id == channel_id,
        )
    ).first()


def list_channel_configs(workspace_id: str, session: Session) -> list[ChatbotChannelConfig]:
    """List channel configs scoped to one workspace."""
    return list(
        session.exec(
            select(ChatbotChannelConfig)
            .where(ChatbotChannelConfig.workspace_id == workspace_id)
            .order_by(ChatbotChannelConfig.channel_type)
        ).all()
    )


def get_channel_config(
    workspace_id: str,
    session: Session,
    channel_type: ChatbotChannelType,
) -> ChatbotChannelConfig | None:
    """Return one workspace-scoped channel config."""
    return session.exec(
        select(ChatbotChannelConfig).where(
            ChatbotChannelConfig.workspace_id == workspace_id,
            ChatbotChannelConfig.channel_type == channel_type,
        )
    ).first()


def get_or_create_bot_config(workspace_id: str, session: Session) -> ChatbotBotConfig:
    """Return the workspace bot config, creating defaults when absent."""
    row = session.exec(
        select(ChatbotBotConfig).where(ChatbotBotConfig.workspace_id == workspace_id)
    ).first()
    if row:
        return row
    row = ChatbotBotConfig(workspace_id=workspace_id)
    session.add(row)
    session.flush()
    return row


def list_knowledge_sources(workspace_id: str, session: Session) -> list[ChatbotKnowledgeSource]:
    """List knowledge sources scoped to one workspace."""
    return list(
        session.exec(
            select(ChatbotKnowledgeSource)
            .where(ChatbotKnowledgeSource.workspace_id == workspace_id)
            .order_by(col(ChatbotKnowledgeSource.created_at).desc())
        ).all()
    )


def get_knowledge_source_by_id(
    workspace_id: str,
    session: Session,
    source_id: object,
) -> ChatbotKnowledgeSource | None:
    """Return one workspace-scoped knowledge source by id."""
    return session.exec(
        select(ChatbotKnowledgeSource).where(
            ChatbotKnowledgeSource.workspace_id == workspace_id,
            ChatbotKnowledgeSource.id == source_id,
        )
    ).first()


def count_chunks_for_source(workspace_id: str, session: Session, source_id: object) -> int:
    """Count chunks for one source without crossing workspace boundaries."""
    return int(
        session.exec(
            select(func.count(ChatbotKnowledgeChunk.id)).where(
                ChatbotKnowledgeChunk.workspace_id == workspace_id,
                ChatbotKnowledgeChunk.source_id == source_id,
            )
        ).one()
    )


def active_index_version(workspace_id: str, session: Session) -> int:
    """Return the latest ready index version for a workspace."""
    value = session.exec(
        select(func.max(ChatbotKnowledgeSource.index_version)).where(
            ChatbotKnowledgeSource.workspace_id == workspace_id,
        )
    ).one()
    return int(value or 1)


def list_conversations(workspace_id: str, session: Session) -> list[ChatbotConversation]:
    """List conversations scoped to one workspace."""
    return list(
        session.exec(
            select(ChatbotConversation)
            .where(
                ChatbotConversation.workspace_id == workspace_id,
                ChatbotConversation.deleted_at.is_(None),
            )
            .order_by(col(ChatbotConversation.last_message_at).desc())
        ).all()
    )


def get_conversation_by_id(
    workspace_id: str,
    session: Session,
    conversation_id: object,
) -> ChatbotConversation | None:
    """Return one non-deleted workspace-scoped conversation."""
    return session.exec(
        select(ChatbotConversation).where(
            ChatbotConversation.workspace_id == workspace_id,
            ChatbotConversation.id == conversation_id,
            ChatbotConversation.deleted_at.is_(None),
        )
    ).first()


def get_or_create_conversation(
    workspace_id: str,
    session: Session,
    *,
    channel_type: ChatbotChannelType,
    visitor_id: str,
    provider_thread_id: str | None = None,
    index_version: int | None = None,
) -> ChatbotConversation:
    """Return one visitor conversation scoped to workspace/channel."""
    row = session.exec(
        select(ChatbotConversation).where(
            ChatbotConversation.workspace_id == workspace_id,
            ChatbotConversation.channel_type == channel_type,
            ChatbotConversation.visitor_id == visitor_id,
        )
    ).first()
    if row:
        return row
    row = ChatbotConversation(
        workspace_id=workspace_id,
        channel_type=channel_type,
        visitor_id=visitor_id,
        provider_thread_id=provider_thread_id,
        index_version=index_version or active_index_version(workspace_id, session),
    )
    session.add(row)
    session.flush()
    return row


def list_recent_messages(
    workspace_id: str,
    session: Session,
    conversation_id: object,
    *,
    limit: int = 10,
) -> list[ChatbotMessage]:
    """Return the most recent messages for a conversation in chronological order."""
    rows = list(
        session.exec(
            select(ChatbotMessage)
            .where(
                ChatbotMessage.workspace_id == workspace_id,
                ChatbotMessage.conversation_id == conversation_id,
                ChatbotMessage.deleted_at.is_(None),
            )
            .order_by(col(ChatbotMessage.created_at).desc())
            .limit(limit)
        ).all()
    )
    return list(reversed(rows))


def count_open_escalations(workspace_id: str, session: Session) -> int:
    """Count unresolved escalations for sidebar badges and inbox summaries."""
    return int(
        session.exec(
            select(func.count(ChatbotConversation.id)).where(
                ChatbotConversation.workspace_id == workspace_id,
                ChatbotConversation.status == ChatbotConversationStatus.escalated,
                ChatbotConversation.deleted_at.is_(None),
            )
        ).one()
    )


def is_visitor_opted_out(
    workspace_id: str,
    session: Session,
    *,
    channel_type: ChatbotChannelType,
    visitor_id: str,
) -> bool:
    """Return whether the visitor has opted out for this workspace/channel."""
    return (
        session.exec(
            select(ChatbotOptOut).where(
                ChatbotOptOut.workspace_id == workspace_id,
                ChatbotOptOut.channel_type == channel_type,
                ChatbotOptOut.visitor_id == visitor_id,
                ChatbotOptOut.reopt_in_invited_at.is_(None),
            )
        ).first()
        is not None
    )


def record_opt_out(
    workspace_id: str,
    session: Session,
    *,
    channel_type: ChatbotChannelType,
    visitor_id: str,
    reason: str | None = None,
    source_message_id: object | None = None,
) -> ChatbotOptOut:
    """Create or return a workspace-scoped visitor opt-out row."""
    row = session.exec(
        select(ChatbotOptOut).where(
            ChatbotOptOut.workspace_id == workspace_id,
            ChatbotOptOut.channel_type == channel_type,
            ChatbotOptOut.visitor_id == visitor_id,
        )
    ).first()
    if row:
        row.reason = reason or row.reason
        row.source_message_id = source_message_id  # type: ignore[assignment]
        row.reopt_in_invited_at = None
        session.add(row)
        session.flush()
        return row
    row = ChatbotOptOut(
        workspace_id=workspace_id,
        channel_type=channel_type,
        visitor_id=visitor_id,
        reason=reason,
        source_message_id=source_message_id,  # type: ignore[arg-type]
    )
    session.add(row)
    session.flush()
    return row


def list_opt_outs(workspace_id: str, session: Session) -> list[ChatbotOptOut]:
    """List opt-outs scoped to one workspace."""
    return list(
        session.exec(
            select(ChatbotOptOut)
            .where(
                ChatbotOptOut.workspace_id == workspace_id,
                ChatbotOptOut.reopt_in_invited_at.is_(None),
            )
            .order_by(col(ChatbotOptOut.created_at).desc())
        ).all()
    )
