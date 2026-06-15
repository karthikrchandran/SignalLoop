from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
    ChatbotOptOut,
)
from app.domain.chatbot.repositories import is_visitor_opted_out, record_opt_out
from app.domain.chatbot.retention import purge_workspace_conversations
from app.domain.chatbot.schemas import ChatbotConfigUpdate
from app.models import User
from app.routers.chatbot.config import get_config, update_config
from app.routers.chatbot.opt_outs import list_opt_out_rows, remove_opt_out


def _session() -> Session:
    _ = AuditEvent
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _user(role: str = "admin") -> User:
    return User(id=uuid.uuid4(), email=f"{role}@example.com", hashed_password="x", role=role)


def test_config_api_validates_compliance_fields_and_audits_update() -> None:
    with _session() as session:
        initial = get_config("ws-a", session, _user())

        assert initial.retention_days == 90

        with pytest.raises(Exception, match="greater than or equal to 30"):
            ChatbotConfigUpdate(retention_days=10)

        updated = update_config(
            ChatbotConfigUpdate(
                ai_disclosure="I am an AI assistant for SignalLoop.",
                retention_days=45,
                token_cap_per_session=5000,
            ),
            "ws-a",
            session,
            _user(),
        )
        audit = session.exec(select(AuditEvent).where(AuditEvent.event_name == "chatbot_config_updated")).first()

        assert updated.retention_days == 45
        assert updated.token_cap_per_session == 5000
        assert audit is not None


def test_opt_out_list_and_admin_reenable_are_workspace_scoped_and_audited() -> None:
    with _session() as session:
        row = ChatbotOptOut(
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.telegram,
            visitor_id="visitor-1",
            reason="stop",
        )
        session.add(row)
        session.add(
            ChatbotOptOut(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.telegram,
                visitor_id="visitor-2",
                reason="stop",
            )
        )
        session.commit()
        session.refresh(row)

        listed = list_opt_out_rows("ws-a", session, _user())
        removed = remove_opt_out(row.id, "ws-a", session, _user())
        remaining = list_opt_out_rows("ws-a", session, _user())
        stored = session.get(ChatbotOptOut, row.id)
        audit = session.exec(select(AuditEvent).where(AuditEvent.event_name == "chatbot_opt_out_removed")).first()

        assert listed.count == 1
        assert removed.removed is True
        assert remaining.count == 0
        assert stored is not None
        assert stored.reopt_in_invited_at is not None
        assert not is_visitor_opted_out(
            "ws-a",
            session,
            channel_type=ChatbotChannelType.telegram,
            visitor_id="visitor-1",
        )
        assert audit is not None

        record_opt_out(
            "ws-a",
            session,
            channel_type=ChatbotChannelType.telegram,
            visitor_id="visitor-1",
            reason="stop again",
        )
        session.commit()

        assert is_visitor_opted_out(
            "ws-a",
            session,
            channel_type=ChatbotChannelType.telegram,
            visitor_id="visitor-1",
        )
        assert list_opt_out_rows("ws-a", session, _user()).count == 1


def test_retention_purge_soft_deletes_old_conversations_by_workspace_and_is_idempotent() -> None:
    with _session() as session:
        session.add(ChatbotBotConfig(workspace_id="ws-a", retention_days=30))
        session.add(ChatbotBotConfig(workspace_id="ws-b", retention_days=30))
        old = ChatbotConversation(
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.facebook_messenger,
            visitor_id="old",
            last_message_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        fresh = ChatbotConversation(
            workspace_id="ws-a",
            channel_type=ChatbotChannelType.facebook_messenger,
            visitor_id="fresh",
            last_message_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        other = ChatbotConversation(
            workspace_id="ws-b",
            channel_type=ChatbotChannelType.facebook_messenger,
            visitor_id="other",
            last_message_at=datetime.now(timezone.utc) - timedelta(days=45),
        )
        session.add(old)
        session.add(fresh)
        session.add(other)
        session.commit()
        session.refresh(old)
        session.refresh(fresh)
        session.refresh(other)
        session.add(
            ChatbotMessage(
                workspace_id="ws-a",
                conversation_id=old.id,
                direction=ChatbotMessageDirection.inbound,
                sender=ChatbotMessageSender.visitor,
                content="old",
            )
        )
        session.commit()

        first = purge_workspace_conversations(session, workspace_id="ws-a")
        session.commit()
        second = purge_workspace_conversations(session, workspace_id="ws-a")
        session.commit()
        session.refresh(old)
        session.refresh(fresh)
        session.refresh(other)

        assert first.conversations_purged == 1
        assert first.messages_purged == 1
        assert second.conversations_purged == 0
        assert old.deleted_at is not None
        assert fresh.deleted_at is None
        assert other.deleted_at is None
