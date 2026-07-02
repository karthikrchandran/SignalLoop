from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
)
from app.domain.chatbot.schemas import ChatbotThreadReplyRequest
from app.domain_models import ContactPublic
from app.models import User
from app.routers.chatbot.inbox import (
    export_threads,
    get_thread,
    list_threads,
    reply_to_thread,
)


def _session() -> Session:
    _ = AuditEvent
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _user(role: str = "agent") -> User:
    return User(id=uuid.uuid4(), email=f"{role}@example.com", hashed_password="x", role=role)


def _request():
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(redis_manager=SimpleNamespace(client=None))))


def _conversation(
    session: Session,
    *,
    workspace_id: str = "ws-a",
    visitor_id: str = "visitor-1",
    channel_type: ChatbotChannelType = ChatbotChannelType.facebook_messenger,
    status: ChatbotConversationStatus = ChatbotConversationStatus.escalated,
    last_message_at: datetime | None = None,
) -> ChatbotConversation:
    conversation = ChatbotConversation(
        workspace_id=workspace_id,
        channel_type=channel_type,
        visitor_id=visitor_id,
        status=status,
        last_message_at=last_message_at or datetime.now(timezone.utc),
        customer_last_message_at=last_message_at or datetime.now(timezone.utc),
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def _message(session: Session, conversation: ChatbotConversation, content: str, sender: ChatbotMessageSender) -> None:
    session.add(
        ChatbotMessage(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            direction=ChatbotMessageDirection.inbound if sender == ChatbotMessageSender.visitor else ChatbotMessageDirection.outbound,
            sender=sender,
            content=content,
        )
    )
    session.commit()


def test_thread_list_filters_workspace_and_returns_ordered_detail() -> None:
    with _session() as session:
        older = _conversation(
            session,
            visitor_id="older",
            last_message_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        newer = _conversation(session, visitor_id="newer")
        other = _conversation(session, workspace_id="ws-b", visitor_id="other")
        _message(session, older, "older visitor", ChatbotMessageSender.visitor)
        _message(session, newer, "newer visitor", ChatbotMessageSender.visitor)
        _message(session, newer, "bot answer", ChatbotMessageSender.bot)
        _message(session, other, "leak", ChatbotMessageSender.visitor)

        result = list_threads("ws-a", session, _user(), limit=10)
        detail = get_thread(newer.id, "ws-a", session, _user())

        assert [row.visitor_id for row in result.data] == ["newer", "older"]
        assert result.count == 2
        assert [message.content for message in detail.messages] == ["newer visitor", "bot answer"]


def test_agent_reply_updates_status_and_appends_message() -> None:
    async def scenario() -> None:
        with _session() as session:
            conversation = _conversation(session)

            result = await reply_to_thread(
                conversation.id,
                body=ChatbotThreadReplyRequest(message="I can help."),
                request=_request(),
                workspace_id="ws-a",
                session=session,
                current_user=_user(),
            )

            assert result.thread.status == ChatbotConversationStatus.agent_active
            assert result.thread.messages[-1].sender == ChatbotMessageSender.agent
            assert result.thread.messages[-1].content == "I can help."

    asyncio.run(scenario())


def test_whatsapp_reply_after_24_hours_returns_clear_error() -> None:
    async def scenario() -> None:
        with _session() as session:
            conversation = _conversation(
                session,
                channel_type=ChatbotChannelType.whatsapp_business,
                last_message_at=datetime.now(timezone.utc) - timedelta(hours=25),
            )
            conversation.customer_last_message_at = datetime.now(timezone.utc) - timedelta(hours=25)
            session.add(conversation)
            session.commit()

            with pytest.raises(Exception) as exc:
                await reply_to_thread(
                    conversation.id,
                    body=ChatbotThreadReplyRequest(message="Hello"),
                    request=_request(),
                    workspace_id="ws-a",
                    session=session,
                    current_user=_user(),
                )

            assert exc.value.status_code == 409
            assert exc.value.detail == "whatsapp_window_expired"

    asyncio.run(scenario())


def test_export_is_workspace_scoped() -> None:
    with _session() as session:
        conversation = _conversation(session, visitor_id="in-scope")
        other = _conversation(session, workspace_id="ws-b", visitor_id="other")
        _message(session, conversation, "in scope", ChatbotMessageSender.visitor)
        _message(session, other, "not in scope", ChatbotMessageSender.visitor)

        response = export_threads("ws-a", session, _user("admin"), format="csv")

        body = response.body.decode()
        assert "in scope" in body
        assert "not in scope" not in body


def test_whatsapp_threads_use_shared_contact_details(monkeypatch: pytest.MonkeyPatch) -> None:
    contact_id = uuid.uuid4()

    def get_shared_contact(**kwargs):
        assert kwargs == {"workspace_id": "ws-a", "contact_id": contact_id}
        return ContactPublic(
            id=contact_id,
            workspace_id="ws-a",
            account_id=None,
            email="ada@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company="Analytical",
            phone="+15551234567",
            timezone="UTC",
            source_channel="whatsapp_business",
            tags_json=["chatbot-lead", "whatsapp_business"],
            intent_json=["demo-request"],
            last_seen_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(
        "app.routers.chatbot.inbox.shared_record_service.get_shared_contact",
        get_shared_contact,
    )

    with _session() as session:
        conversation = _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            visitor_id="15551234567",
        )
        conversation.shared_contact_id = contact_id
        session.add(conversation)
        session.commit()

        result = list_threads("ws-a", session, _user(), limit=10)

    assert result.data[0].lead is not None
    assert result.data[0].lead.email == "ada@example.com"
    assert result.data[0].lead.source_channel == "whatsapp_business"
    assert "chatbot-lead" in result.data[0].lead.tags
