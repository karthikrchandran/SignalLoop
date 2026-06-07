from __future__ import annotations

import asyncio

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.engine import BotRuntimeInput, ConversationEngine
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotLeadCaptureState,
)
from app.domain_models import Contact
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


def test_lead_capture_requires_consent_then_upserts_contact() -> None:
    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
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
            contact = session.exec(select(Contact)).one()
            captured_event = session.exec(
                select(AuditEvent).where(AuditEvent.event_name == "chatbot_lead_captured")
            ).one()

            assert third.reason == "lead_capture"
            assert conversation.lead_capture_state == ChatbotLeadCaptureState.confirmed
            assert conversation.outcome == ChatbotConversationOutcome.lead_captured
            assert conversation.contact_id == contact.id
            assert contact.email == "ada@example.com"
            assert contact.first_name == "Ada"
            assert contact.last_name == "Lovelace"
            assert contact.source_channel == ChatbotChannelType.whatsapp_business.value
            assert "chatbot-lead" in contact.tags_json
            assert "demo-request" in contact.intent_json
            assert captured_event.resource_id == str(contact.id)

    asyncio.run(scenario())


def test_phone_only_lead_deduplicates_by_phone_with_placeholder_email() -> None:
    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
            engine = ConversationEngine(session=session, adapter=adapter)
            await engine.process(_input("pricing please", "p1"))
            await engine.process(_input("yes", "p2"))
            await engine.process(_input("Grace Hopper +1 555 123 9999", "p3"))

            contact = session.exec(select(Contact)).one()
            assert contact.email.endswith("@chatbot.local.invalid")
            assert contact.phone == "+15551239999"

            await engine.process(_input("pricing please again", "p4"))
            await engine.process(_input("yes", "p5"))
            await engine.process(_input("Grace Hopper +1 555 123 9999", "p6"))

            contacts = session.exec(select(Contact)).all()
            assert len(contacts) == 1
            assert contacts[0].intent_json == ["pricing-request"]

    asyncio.run(scenario())

