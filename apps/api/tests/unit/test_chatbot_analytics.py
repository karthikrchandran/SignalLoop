from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
    ChatbotOptOut,
)
from app.domain.sequences.models import ContactSequenceState, EmailSequence
from app.domain.voice.models import CallRequest, VoiceScript
from app.domain_models import (
    Campaign,
    Contact,
    ContactProgression,
    ContactProgressionState,
    ProspectingSnapshot,
)
from app.models import User
from app.routers.chatbot.analytics import get_chatbot_analytics


def _session() -> Session:
    _ = AuditEvent
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _user() -> User:
    return User(email="agent@example.com", hashed_password="x", role="agent")


def _conversation(
    session: Session,
    *,
    channel_type: ChatbotChannelType,
    outcome: ChatbotConversationOutcome | None,
    last_message_at: datetime,
    contact_id: uuid.UUID | None = None,
    escalated: bool = False,
) -> ChatbotConversation:
    row = ChatbotConversation(
        workspace_id="ws-a",
        channel_type=channel_type,
        visitor_id=f"{channel_type.value}-{outcome or 'open'}-{last_message_at.timestamp()}",
        contact_id=contact_id,
        outcome=outcome,
        escalated=escalated,
        last_message_at=last_message_at,
        updated_at=last_message_at,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _bot_message(session: Session, conversation: ChatbotConversation, created_at: datetime) -> None:
    session.add(
        ChatbotMessage(
            workspace_id=conversation.workspace_id,
            conversation_id=conversation.id,
            direction=ChatbotMessageDirection.outbound,
            sender=ChatbotMessageSender.bot,
            content="Answer",
            created_at=created_at,
        )
    )
    session.commit()


def test_chatbot_analytics_aggregates_workspace_range() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        resolved = _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        lead = _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.lead_captured,
            last_message_at=now - timedelta(days=1),
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.telegram,
            outcome=ChatbotConversationOutcome.escalated,
            last_message_at=now,
            escalated=True,
        )
        session.add(
            ChatbotConversation(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.telegram,
                visitor_id="other-workspace",
                outcome=ChatbotConversationOutcome.escalated,
                escalated=True,
                last_message_at=now,
            )
        )
        _bot_message(session, resolved, now)
        _bot_message(session, lead, now - timedelta(days=1))
        session.add(
            ChatbotOptOut(
                workspace_id="ws-a",
                channel_type=ChatbotChannelType.whatsapp_business,
                visitor_id="15551234567",
                created_at=now,
            )
        )
        session.commit()

        result = get_chatbot_analytics(
            "ws-a",
            session,
            _user(),
            date_from=(now - timedelta(days=1)).date(),
            date_to=now.date(),
        )

        assert result.totals.conversations == 3
        assert result.totals.bot_messages == 2
        assert result.totals.leads_captured == 1
        assert result.totals.escalations == 1
        assert result.totals.opt_outs == 1
        assert result.totals.containment_rate == 33.3
        assert [point.conversations for point in result.timeseries] == [1, 2]
        whatsapp = next(row for row in result.channel_breakdown if row.channel_type == ChatbotChannelType.whatsapp_business)
        assert whatsapp.bot_resolved == 1
        assert whatsapp.lead_captured == 1
        assert whatsapp.opted_out == 1


def test_chatbot_analytics_tracks_conversion_funnel_to_campaign_and_voice_followup() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        contact = Contact(
            workspace_id="ws-a",
            email="maya@example.com",
            first_name="Maya",
            last_name="Singh",
            company="Northstar Clinics",
            phone="+15550199000",
            source_channel="whatsapp_business",
        )
        campaign = Campaign(name="Chatbot Leads", workspace_id="ws-a", created_by=uuid.uuid4())
        session.add(contact)
        session.add(campaign)
        session.commit()
        session.refresh(contact)
        session.refresh(campaign)

        sequence = EmailSequence(campaign_id=campaign.id, name="Prospecting Sequence", created_by=uuid.uuid4())
        script = VoiceScript(
            campaign_id=campaign.id,
            name="Warm handoff",
            content="Open with chatbot context",
            created_by=uuid.uuid4(),
        )
        session.add(sequence)
        session.add(script)
        session.commit()
        session.refresh(sequence)
        session.refresh(script)

        _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.lead_captured,
            contact_id=contact.id,
            last_message_at=now,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.telegram,
            outcome=ChatbotConversationOutcome.lead_captured,
            last_message_at=now,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.facebook_messenger,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        session.add(
            ProspectingSnapshot(
                workspace_id="ws-a",
                contact_id=contact.id,
                email_draft="Hi Maya, saw your growth plans...",
                voice_opener="Mention the three-location pricing question.",
            )
        )
        session.add(
            ContactProgression(
                contact_id=contact.id,
                campaign_id=campaign.id,
                current_state=ContactProgressionState.inbox,
            )
        )
        session.add(ContactSequenceState(contact_id=contact.id, sequence_id=sequence.id))
        session.add(
            CallRequest(
                contact_id=contact.id,
                campaign_id=campaign.id,
                voice_script_id=script.id,
                trigger_reason="chatbot_lead_followup",
                scheduled_at=now + timedelta(hours=1),
            )
        )
        session.commit()

        result = get_chatbot_analytics(
            "ws-a",
            session,
            _user(),
            date_from=now.date(),
            date_to=now.date(),
        )

        assert result.conversion_funnel.conversations == 3
        assert result.conversion_funnel.leads_captured == 2
        assert result.conversion_funnel.prospecting_researched == 1
        assert result.conversion_funnel.added_to_campaign == 1
        assert result.conversion_funnel.sequence_enrolled == 1
        assert result.conversion_funnel.voice_followups == 1
