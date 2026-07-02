from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot import lead_capture as lead_capture_module
from app.domain.chatbot.engine import BotRuntimeInput, ConversationEngine
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotLeadCaptureState,
)
from app.domain_models import Contact, ContactPublic
from app.infrastructure.providers.chat.base import ChatDeliveryReceipt


class FakeAdapter:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, _visitor_id: str, text: str) -> ChatDeliveryReceipt:
        self.sent.append(text)
        return ChatDeliveryReceipt(accepted=True, provider_message_id=f"lead-{len(self.sent)}")


def _session() -> Session:
    _ = AuditEvent
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _input(text: str, message_id: str) -> BotRuntimeInput:
    return BotRuntimeInput(
        workspace_id="ws-leads",
        channel_type=ChatbotChannelType.whatsapp_business,
        visitor_id="15551234567",
        provider_message_id=message_id,
        text=text,
        is_text=True,
        is_opt_out=False,
        raw_payload={"text": text},
    )


def test_lead_capture_requires_consent_then_upserts_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
            shared_calls: list[dict[str, object]] = []

            def upsert_shared_contact(**kwargs):
                shared_calls.append(kwargs)
                return ContactPublic(
                    id=kwargs["contact_id"],
                    workspace_id=kwargs["workspace_id"],
                    account_id=None,
                    email=kwargs["email"],
                    first_name=kwargs["first_name"],
                    last_name=kwargs["last_name"],
                    company=kwargs["company"],
                    phone=kwargs["phone"],
                    timezone=kwargs["timezone"],
                    source_channel=kwargs["source_channel"],
                    tags_json=list(kwargs["tags_json"]),
                    intent_json=list(kwargs["intent_json"]),
                    last_seen_at=kwargs["last_seen_at"],
                    created_at=datetime.now(timezone.utc),
                )

            monkeypatch.setattr(
                lead_capture_module.shared_record_service,
                "upsert_shared_contact",
                upsert_shared_contact,
            )
            engine = ConversationEngine(session=session, adapter=adapter)

            first = await engine.process(_input("I want to book a demo", "m1"))
            conversation = session.exec(select(ChatbotConversation)).one()

            assert first.reason == "lead_capture"
            assert conversation.lead_capture_state == ChatbotLeadCaptureState.privacy_notice_prompt
            assert conversation.lead_capture_intent == "demo-request"
            assert session.exec(select(Contact)).first() is None
            assert "Reply yes" in adapter.sent[-1]

            second = await engine.process(_input("yes, I agree", "m2"))
            session.refresh(conversation)

            assert second.reason == "lead_capture"
            assert conversation.lead_capture_state == ChatbotLeadCaptureState.collecting
            assert session.exec(select(AuditEvent).where(AuditEvent.event_name == "chatbot_lead_consent_accepted")).first()

            third = await engine.process(_input("Ada Lovelace ada@example.com", "m3"))
            session.refresh(conversation)
            captured_event = session.exec(
                select(AuditEvent).where(AuditEvent.event_name == "chatbot_lead_captured")
            ).one()

            assert third.reason == "lead_capture"
            assert conversation.lead_capture_state == ChatbotLeadCaptureState.confirmed
            assert conversation.outcome == ChatbotConversationOutcome.lead_captured
            assert session.exec(select(Contact)).first() is None
            assert conversation.contact_id == shared_calls[-1]["contact_id"]
            assert shared_calls[-1]["email"] == "ada@example.com"
            assert shared_calls[-1]["first_name"] == "Ada"
            assert shared_calls[-1]["last_name"] == "Lovelace"
            assert shared_calls[-1]["source_channel"] == ChatbotChannelType.whatsapp_business.value
            assert "chatbot-lead" in shared_calls[-1]["tags_json"]
            assert "demo-request" in shared_calls[-1]["intent_json"]
            assert captured_event.resource_id == str(shared_calls[-1]["contact_id"])

    asyncio.run(scenario())


def test_phone_only_lead_deduplicates_by_phone_with_placeholder_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
            shared_calls: list[dict[str, object]] = []

            def upsert_shared_contact(**kwargs):
                shared_calls.append(kwargs)
                return ContactPublic(
                    id=kwargs["contact_id"],
                    workspace_id=kwargs["workspace_id"],
                    account_id=None,
                    email=kwargs["email"],
                    first_name=kwargs["first_name"],
                    last_name=kwargs["last_name"],
                    company=kwargs["company"],
                    phone=kwargs["phone"],
                    timezone=kwargs["timezone"],
                    source_channel=kwargs["source_channel"],
                    tags_json=list(kwargs["tags_json"]),
                    intent_json=list(kwargs["intent_json"]),
                    last_seen_at=kwargs["last_seen_at"],
                    created_at=datetime.now(timezone.utc),
                )

            monkeypatch.setattr(
                lead_capture_module.shared_record_service,
                "upsert_shared_contact",
                upsert_shared_contact,
            )
            engine = ConversationEngine(session=session, adapter=adapter)
            await engine.process(_input("pricing please", "p1"))
            await engine.process(_input("yes", "p2"))
            await engine.process(_input("Grace Hopper +1 555 123 9999", "p3"))

            assert session.exec(select(Contact)).first() is None
            first_contact_id = shared_calls[-1]["contact_id"]
            assert shared_calls[-1]["email"].endswith("@chatbot.local.invalid")
            assert shared_calls[-1]["phone"] == "+15551239999"

            await engine.process(_input("pricing please again", "p4"))
            await engine.process(_input("yes", "p5"))
            await engine.process(_input("Grace Hopper +1 555 123 9999", "p6"))

            assert len(shared_calls) == 2
            assert shared_calls[1]["contact_id"] == first_contact_id
            assert shared_calls[0]["intent_json"] == ["pricing-request"]
            assert shared_calls[1]["intent_json"] == ["pricing-request"]

    asyncio.run(scenario())
