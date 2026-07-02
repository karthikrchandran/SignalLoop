from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.analytics_snapshots import (
    refresh_all_chatbot_analytics_snapshots,
    refresh_chatbot_analytics_snapshots,
)
from app.domain.chatbot.models import (
    ChatbotAnalyticsSnapshot,
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
from app.workers.chatbot_analytics_snapshot_job import (
    _target_date_from_env,
    run_chatbot_analytics_snapshot_job,
)


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


def test_refresh_chatbot_analytics_snapshots_materializes_workspace_channel_metrics() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        resolved = _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.lead_captured,
            last_message_at=now,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.escalated,
            last_message_at=now,
            escalated=True,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.telegram,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=None,
            last_message_at=now,
        )
        session.add(
            ChatbotConversation(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.whatsapp_business,
                visitor_id="other-workspace",
                outcome=ChatbotConversationOutcome.lead_captured,
                last_message_at=now,
            )
        )
        _bot_message(session, resolved, now)
        _bot_message(session, resolved, now - timedelta(days=2))
        session.add(
            ChatbotOptOut(
                workspace_id="ws-a",
                channel_type=ChatbotChannelType.whatsapp_business,
                visitor_id="15551234567",
                created_at=now,
            )
        )
        session.commit()

        result = refresh_chatbot_analytics_snapshots(session, workspace_id="ws-a", target_date=now.date())

        assert result == 2
        snapshots = list(session.exec(select(ChatbotAnalyticsSnapshot)).all())
        assert len(snapshots) == 2
        whatsapp = next(row for row in snapshots if row.channel_type == ChatbotChannelType.whatsapp_business)
        assert whatsapp.workspace_id == "ws-a"
        assert whatsapp.snapshot_date == now.date()
        assert whatsapp.total_conversations == 4
        assert whatsapp.bot_messages == 1
        assert whatsapp.escalations == 1
        assert whatsapp.leads_captured == 1
        assert whatsapp.metrics_json["bot_resolved"] == 1
        assert whatsapp.metrics_json["opt_outs"] == 1


def test_refresh_chatbot_analytics_snapshots_rebuilds_existing_rows_for_date() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        first = _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        result = refresh_chatbot_analytics_snapshots(session, workspace_id="ws-a", target_date=now.date())
        assert result == 1
        assert len(list(session.exec(select(ChatbotAnalyticsSnapshot)).all())) == 1

        first.deleted_at = now
        session.add(first)
        session.commit()

        result = refresh_chatbot_analytics_snapshots(session, workspace_id="ws-a", target_date=now.date())
        assert result == 0
        assert len(list(session.exec(select(ChatbotAnalyticsSnapshot)).all())) == 0


def test_refresh_all_chatbot_analytics_snapshots_discovers_active_workspaces() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        _conversation(
            session,
            channel_type=ChatbotChannelType.whatsapp_business,
            outcome=ChatbotConversationOutcome.bot_resolved,
            last_message_at=now,
        )
        session.add(
            ChatbotConversation(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.telegram,
                visitor_id="ws-b-visitor",
                outcome=ChatbotConversationOutcome.lead_captured,
                last_message_at=now,
            )
        )
        session.commit()

        result = refresh_all_chatbot_analytics_snapshots(session, target_date=now.date())

        assert result == {"ws-a": 1, "ws-b": 1}
        snapshots = list(session.exec(select(ChatbotAnalyticsSnapshot)).all())
        assert {snapshot.workspace_id for snapshot in snapshots} == {"ws-a", "ws-b"}


def test_chatbot_analytics_snapshot_job_runs_against_supplied_session() -> None:
    now = datetime(2026, 6, 7, 12, 0, tzinfo=timezone.utc)
    with _session() as session:
        _conversation(
            session,
            channel_type=ChatbotChannelType.telegram,
            outcome=ChatbotConversationOutcome.lead_captured,
            last_message_at=now,
        )

        result = run_chatbot_analytics_snapshot_job(target_date=now.date(), session=session)

        assert result == {"ws-a": 1}
        snapshot = session.exec(select(ChatbotAnalyticsSnapshot)).one()
        assert snapshot.channel_type == ChatbotChannelType.telegram
        assert snapshot.leads_captured == 1


def test_target_date_from_env_ignores_invalid_value(monkeypatch) -> None:
    monkeypatch.setenv("CHATBOT_ANALYTICS_SNAPSHOT_DATE", "not-a-date")
    assert _target_date_from_env() is None
