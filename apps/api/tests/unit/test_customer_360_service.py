from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.chatbot.models import (
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
)
from app.domain.customer_360.service import (
    get_account_profile,
    list_customer_360_accounts,
)
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailEvent,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
)
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import Account, Campaign, Contact, ProspectingSnapshot


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_account(
    session: Session,
    *,
    workspace_id: str = "ws-a",
) -> tuple[Account, Contact, Contact]:
    owner_id = uuid.uuid4()
    account = Account(
        workspace_id=workspace_id,
        name="Analytical Health",
        account_key="analytical-health",
        summary="Multi-location healthcare buyer.",
        tags_json=["pricing", "voice-ready"],
    )
    session.add(account)
    session.flush()

    ada = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical Health",
        phone="+15551234567",
    )
    grace = Contact(
        workspace_id=workspace_id,
        account_id=account.id,
        email="grace@example.com",
        first_name="Grace",
        last_name="Hopper",
        company="Analytical Health",
    )
    session.add(ada)
    session.add(grace)
    session.flush()

    campaign = Campaign(name="Q2 Outreach", workspace_id=workspace_id, created_by=owner_id)
    session.add(campaign)
    session.flush()

    conversation = ChatbotConversation(
        workspace_id=workspace_id,
        channel_type=ChatbotChannelType.whatsapp_business,
        visitor_id="visitor-ada",
        contact_id=ada.id,
        status=ChatbotConversationStatus.escalated,
        escalated=True,
        escalation_reason="Pricing question needs a human",
        last_message_at=datetime.now(timezone.utc) - timedelta(minutes=20),
    )
    session.add(conversation)
    session.flush()
    session.add(
        ChatbotMessage(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            direction=ChatbotMessageDirection.inbound,
            sender=ChatbotMessageSender.visitor,
            content="Can you explain pricing for three locations?",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
    )

    script = VoiceScript(
        campaign_id=campaign.id,
        name="Discovery",
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
        scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=15),
    )
    session.add(call_request)
    session.flush()
    session.add(
        CallSession(
            call_request_id=call_request.id,
            outcome=CallOutcome.answered,
            duration_seconds=96,
            transcript="Ada needs implementation pricing clarity before booking.",
            unanswered_questions={"questions": ["implementation pricing clarity"]},
            scheduling_interest=True,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=12),
        )
    )

    sequence = EmailSequence(
        campaign_id=campaign.id,
        name="Welcome",
        active=True,
        created_by=owner_id,
    )
    session.add(sequence)
    session.flush()
    sequence_state = ContactSequenceState(contact_id=grace.id, sequence_id=sequence.id)
    session.add(sequence_state)
    session.flush()
    send_request = SendRequest(
        contact_sequence_state_id=sequence_state.id,
        step_order=1,
        idempotency_key=f"{workspace_id}-grace-step-1",
        status=SendRequestStatus.sent,
        sent_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    session.add(send_request)
    session.flush()
    session.add(
        EmailEvent(
            send_request_id=send_request.id,
            event_type="opened",
            timestamp=datetime.now(timezone.utc) - timedelta(hours=23),
        )
    )

    session.add(
        ProspectingSnapshot(
            workspace_id=workspace_id,
            contact_id=ada.id,
            company_url="https://analytical.example",
            sources_json=[
                {"label": "CRM contact", "summary": "Ada at Analytical Health"}
            ],
            research_json={
                "account_summary": (
                    "Analytical Health is evaluating cross-channel outreach."
                ),
                "suggested_next_action": (
                    "Reply with pricing clarity, then queue a call."
                ),
            },
            email_draft="Subject: Analytical Health follow-up",
            voice_opener="Hi Ada, following up on pricing.",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    session.commit()
    return account, ada, grace


def test_list_customer_360_accounts_returns_account_rollups() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(session)

        result = list_customer_360_accounts(session, workspace_id="ws-a")

    assert result.count == 1
    row = result.data[0]
    assert row.id == account.id
    assert row.name == "Analytical Health"
    assert row.contact_count == 2
    assert row.channel_counts["chatbot"] == 1
    assert row.channel_counts["email"] == 1
    assert row.channel_counts["voice"] == 1
    assert row.channel_counts["prospecting"] == 1
    assert row.top_next_action == "Reply with pricing clarity, then queue a call."


def test_get_account_profile_aggregates_contacts_channels_and_timeline() -> None:
    with _session() as session:
        account, ada, grace = _seed_account(session)

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile is not None
    assert profile.account.id == account.id
    assert {contact.email for contact in profile.contacts} == {
        "ada@example.com",
        "grace@example.com",
    }
    assert profile.channel_summaries["chatbot"].count == 1
    assert profile.channel_summaries["email"].count == 1
    assert profile.channel_summaries["voice"].count == 1
    assert profile.channel_summaries["prospecting"].count == 1
    assert profile.next_best_action is not None
    assert profile.next_best_action.title == "Reply with pricing clarity, then queue a call"
    assert profile.prospecting_brief is not None
    assert (
        profile.prospecting_brief.account_summary
        == "Analytical Health is evaluating cross-channel outreach."
    )
    assert {event.contact_id for event in profile.timeline} == {ada.id, grace.id}
    assert [event.timestamp for event in profile.timeline] == sorted(
        [event.timestamp for event in profile.timeline],
        reverse=True,
    )


def test_get_account_profile_returns_none_for_wrong_workspace() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(session)

        profile = get_account_profile(session, workspace_id="ws-b", account_id=account.id)

    assert profile is None
