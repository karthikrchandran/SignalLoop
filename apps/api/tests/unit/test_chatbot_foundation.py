from __future__ import annotations

import inspect

from sqlmodel import Session, SQLModel, create_engine

from app.domain.chatbot import repositories
from app.domain.chatbot.models import (
    ChatbotAnalyticsSnapshot,
    ChatbotBotConfig,
    ChatbotChannelConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotKnowledgeChunk,
    ChatbotKnowledgeSource,
    ChatbotKnowledgeSourceType,
    ChatbotMessage,
    ChatbotOptOut,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_repository_functions_take_workspace_id_first() -> None:
    guarded_functions = [
        repositories.count_open_escalations,
        repositories.get_channel_config,
        repositories.list_channel_configs,
        repositories.list_conversations,
        repositories.list_knowledge_sources,
        repositories.list_opt_outs,
    ]

    for function in guarded_functions:
        first_parameter = next(iter(inspect.signature(function).parameters.values()))
        assert first_parameter.name == "workspace_id"


def test_foundation_tables_include_workspace_id() -> None:
    foundation_models = [
        ChatbotAnalyticsSnapshot,
        ChatbotBotConfig,
        ChatbotChannelConfig,
        ChatbotConversation,
        ChatbotKnowledgeChunk,
        ChatbotKnowledgeSource,
        ChatbotMessage,
        ChatbotOptOut,
    ]

    for model in foundation_models:
        assert "workspace_id" in model.model_fields


def test_channel_repository_is_workspace_scoped() -> None:
    with _session() as session:
        session.add(
            ChatbotChannelConfig(
                workspace_id="ws-a",
                channel_type=ChatbotChannelType.facebook_messenger,
                display_name="Messenger A",
            )
        )
        session.add(
            ChatbotChannelConfig(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.whatsapp_business,
                display_name="WhatsApp B",
            )
        )
        session.commit()

        rows = repositories.list_channel_configs("ws-a", session)

        assert [row.workspace_id for row in rows] == ["ws-a"]
        assert repositories.get_channel_config(
            "ws-b",
            session,
            ChatbotChannelType.facebook_messenger,
        ) is None


def test_conversation_knowledge_and_opt_out_repositories_are_workspace_scoped() -> None:
    with _session() as session:
        for workspace_id in ("ws-a", "ws-b"):
            session.add(
                ChatbotConversation(
                    workspace_id=workspace_id,
                    channel_type=ChatbotChannelType.facebook_messenger,
                    visitor_id=f"visitor-{workspace_id}",
                    status=ChatbotConversationStatus.escalated,
                )
            )
            session.add(
                ChatbotKnowledgeSource(
                    workspace_id=workspace_id,
                    source_type=ChatbotKnowledgeSourceType.faq,
                    title=f"FAQ {workspace_id}",
                )
            )
            session.add(
                ChatbotOptOut(
                    workspace_id=workspace_id,
                    channel_type=ChatbotChannelType.facebook_messenger,
                    visitor_id=f"visitor-{workspace_id}",
                )
            )
        session.commit()

        assert [row.workspace_id for row in repositories.list_conversations("ws-a", session)] == ["ws-a"]
        assert [row.workspace_id for row in repositories.list_knowledge_sources("ws-b", session)] == ["ws-b"]
        assert [row.workspace_id for row in repositories.list_opt_outs("ws-a", session)] == ["ws-a"]
        assert repositories.count_open_escalations("ws-a", session) == 1
