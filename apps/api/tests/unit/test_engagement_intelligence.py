from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

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
from app.domain.engagement_intelligence.service import build_engagement_overview
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
)
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import (
    Campaign,
    Contact,
    ContactProgression,
    ContactProgressionState,
    NotificationProvider,
    OfferPack,
    ProspectingSnapshot,
    ProviderEventLog,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_workspace(session: Session, *, workspace_id: str = "ws-a") -> None:
    owner_id = uuid.uuid4()
    campaign = Campaign(
        name="Q2 Outreach",
        workspace_id=workspace_id,
        created_by=owner_id,
    )
    session.add(campaign)
    session.flush()

    ada = Contact(
        workspace_id=workspace_id,
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical",
        phone="+15551234567",
        tags_json=["chatbot-lead"],
        intent_json=["pricing-request"],
        source_channel="whatsapp",
    )
    grace = Contact(
        workspace_id=workspace_id,
        email="grace@example.com",
        first_name="Grace",
        last_name="Hopper",
        company="Compiler Co",
        phone="+15559876543",
    )
    session.add(ada)
    session.add(grace)
    session.flush()

    conversation = ChatbotConversation(
        workspace_id=workspace_id,
        channel_type=ChatbotChannelType.whatsapp_business,
        visitor_id="visitor-ada",
        contact_id=ada.id,
        status=ChatbotConversationStatus.escalated,
        escalated=True,
        escalation_reason="Pricing question needs a human",
        lead_capture_intent="pricing",
        consecutive_low_confidence_count=2,
        last_message_at=datetime.now(timezone.utc),
    )
    session.add(conversation)
    session.flush()
    session.add(
        ChatbotMessage(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            direction=ChatbotMessageDirection.inbound,
            sender=ChatbotMessageSender.visitor,
            content="Can you explain pricing and implementation?",
        )
    )

    script = VoiceScript(
        campaign_id=campaign.id,
        name="Discovery script",
        content="Hi.",
        created_by=owner_id,
    )
    session.add(script)
    session.flush()
    call_request = CallRequest(
        contact_id=ada.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_test_call",
        scheduled_at=datetime.now(timezone.utc),
    )
    session.add(call_request)
    session.flush()
    session.add(
        CallSession(
            call_request_id=call_request.id,
            twilio_call_sid="CA123",
            outcome=CallOutcome.answered,
            duration_seconds=120,
            transcript="Ada is interested but needs implementation pricing clarity.",
            unanswered_questions={"questions": ["implementation pricing clarity"]},
            scheduling_interest=True,
        )
    )

    sequence = EmailSequence(
        campaign_id=campaign.id,
        name="Welcome sequence",
        active=True,
        created_by=owner_id,
    )
    session.add(sequence)
    session.flush()
    sequence_state = ContactSequenceState(
        contact_id=ada.id,
        sequence_id=sequence.id,
        next_send_at=datetime.now(timezone.utc) - timedelta(hours=6),
    )
    session.add(sequence_state)
    session.flush()
    session.add(
        SendRequest(
            contact_sequence_state_id=sequence_state.id,
            step_order=1,
            idempotency_key=f"{workspace_id}-ada-step-1",
            status=SendRequestStatus.failed,
            retry_count=3,
        )
    )
    session.add(
        ContactProgression(
            contact_id=ada.id,
            campaign_id=campaign.id,
            current_state=ContactProgressionState.engaged,
            last_action_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
    )

    session.add(
        ProspectingSnapshot(
            workspace_id=workspace_id,
            contact_id=grace.id,
            company_url="https://compiler.example",
            sources_json=[{"label": "CRM contact", "summary": "Grace at Compiler Co"}],
            research_json={
                "account_summary": "Grace is evaluating outreach automation.",
                "pain_points": ["Keep follow-up coordinated."],
                "objections": ["Needs security details."],
                "personalization_bullets": ["Mention Compiler Co."],
                "suggested_next_action": "Send personalized outreach.",
                "email_draft": "Subject: Compiler Co follow-up",
                "voice_opener": "Hi Grace.",
            },
            email_draft="Subject: Compiler Co follow-up",
            voice_opener="Hi Grace.",
        )
    )
    session.add(
        OfferPack(
            workspace_id=workspace_id, name="Starter Demo Pack", created_by=owner_id
        )
    )
    session.add(
        ProviderEventLog(
            workspace_id=workspace_id,
            provider=NotificationProvider.sendgrid,
            provider_event_id=f"{workspace_id}-sendgrid-delivered",
            event_type="delivered",
            normalized_event={"channel": "email"},
        )
    )
    session.add(
        ProviderEventLog(
            workspace_id=workspace_id,
            provider=NotificationProvider.sendgrid,
            provider_event_id=f"{workspace_id}-sendgrid-bounce",
            event_type="bounce",
            normalized_event={"channel": "email", "reason": "mailbox unavailable"},
        )
    )
    session.add(
        AuditEvent(
            event_name="prospect.researched",
            workspace_id=workspace_id,
            actor_role="admin",
            resource_type="prospecting_snapshot",
            resource_id=str(grace.id),
            payload={"summary": "Generated Compiler Co research and outreach draft."},
        )
    )

    other = Contact(
        workspace_id="ws-b",
        email="other@example.com",
        first_name="Other",
        last_name="Workspace",
        company="Elsewhere",
    )
    session.add(other)
    session.commit()


def test_engagement_overview_ranks_actions_and_unifies_work_queue() -> None:
    with _session() as session:
        _seed_workspace(session)

        overview = build_engagement_overview(session, workspace_id="ws-a")

    action_titles = [action.title for action in overview.next_best_actions]
    assert action_titles[:3] == [
        "Book meeting from voice call",
        "Reply to escalated chatbot thread",
        "Enroll researched prospect in sequence",
    ]
    assert {item.source for item in overview.unified_inbox} == {
        "chatbot",
        "voice",
        "prospecting",
    }
    assert [stage.id for stage in overview.journey.stages] == [
        "chatbot_capture",
        "prospecting_research",
        "sequence_enrollment",
        "voice_follow_up",
        "sales_handoff",
    ]
    assert overview.journey.stages[0].count == 1
    assert overview.journey.stages[1].count == 1
    assert overview.knowledge_gaps[0].title == "Pricing clarity"
    assert overview.offer_recommendations[0].title == "Use Starter Demo Pack"
    assert overview.experiment_recommendations[0].title == (
        "Pricing clarity holdout test"
    )
    assert overview.experiment_recommendations[0].holdout_percent == 10
    assert overview.audit_replay[0].event_name == "prospect.researched"
    assert overview.audit_replay[0].actor_role == "admin"
    sendgrid_health = next(
        item for item in overview.provider_health if item.provider == "sendgrid"
    )
    assert sendgrid_health.status == "needs_attention"
    assert sendgrid_health.success_count == 1
    assert sendgrid_health.failure_count == 2
    assert "Review failed sendgrid delivery events" in (
        sendgrid_health.recommended_action
    )
    assert overview.pipeline_risks[0].contact_name == "Ada Lovelace"
    assert overview.pipeline_risks[0].risk_level == "high"
    assert overview.pipeline_risks[0].reasons == [
        "Open chatbot escalation",
        "Answered voice call is waiting for scheduling",
        "Failed email send",
        "Stalled active sequence",
        "Engaged contact has no recent action",
    ]


def test_engagement_overview_is_workspace_scoped() -> None:
    with _session() as session:
        _seed_workspace(session)

        overview = build_engagement_overview(session, workspace_id="ws-b")

    assert overview.next_best_actions == []
    assert overview.unified_inbox == []
    assert all(stage.count == 0 for stage in overview.journey.stages)
    assert overview.knowledge_gaps == []
    assert overview.offer_recommendations == []
    assert overview.experiment_recommendations == []
    assert overview.audit_replay == []
    assert overview.provider_health == []
    assert overview.pipeline_risks == []
