from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

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
from app.domain.shared_records import service as shared_service
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import Account, Campaign, Contact, ProspectingSnapshot
from app.integrations.ecrm_shared_records import EcrmSharedRecordNotFound

_SHARED_RECORDS: dict[str, dict[str, object]] = {}


@pytest.fixture(autouse=True)
def _shared_record_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    _SHARED_RECORDS.clear()

    def list_shared_records(**kwargs):  # noqa: ANN001
        entity_type = kwargs.get("entity_type")
        q = str(kwargs.get("q") or "").lower()
        status = kwargs.get("status")
        parent_id = kwargs.get("parent_id")
        records = list(_SHARED_RECORDS.values())
        if entity_type:
            records = [
                record
                for record in records
                if str(record.get("entityType") or "").upper()
                == str(entity_type).upper()
            ]
        if status is not None:
            records = [
                record
                for record in records
                if str(record.get("status") or "").lower() == str(status).lower()
            ]
        if parent_id is not None:
            records = [
                record
                for record in records
                if str(record.get("parentId") or "") == str(parent_id)
            ]
        if q:
            records = [
                record
                for record in records
                if q
                in " ".join(
                    str(record.get(field) or "")
                    for field in ("displayName", "companyName", "email")
                ).lower()
            ]
        limit = kwargs.get("limit")
        if isinstance(limit, int):
            records = records[:limit]
        return {"records": records}

    def get_shared_record(record_id: str) -> dict[str, object]:
        record = _SHARED_RECORDS.get(record_id)
        if record is None:
            raise EcrmSharedRecordNotFound(record_id)
        return record

    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "list_shared_records",
        list_shared_records,
    )
    monkeypatch.setattr(
        shared_service.ecrm_shared_records,
        "get_shared_record",
        get_shared_record,
    )


def _register_shared_account(account: Account) -> None:
    _SHARED_RECORDS[str(account.id)] = {
        "id": str(account.id),
        "entityType": "CUSTOMER",
        "displayName": account.name,
        "status": "active",
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(account.id),
        "externalKey": f"emailvoice:account:{account.workspace_id}:{account.account_key}",
        "companyName": account.name,
        "data": {
            "workspaceId": account.workspace_id,
            "accountKey": account.account_key,
            "summary": account.summary,
            "tags": list(account.tags_json or []),
        },
        "createdAt": account.created_at.isoformat(),
        "updatedAt": account.updated_at.isoformat(),
    }


def _register_shared_contact(contact: Contact, *, parent_id: uuid.UUID | None = None) -> None:
    payload: dict[str, object] = {
        "id": str(contact.id),
        "entityType": "CONTACT",
        "displayName": " ".join(
            part for part in [contact.first_name, contact.last_name] if part
        ).strip()
        or contact.email,
        "status": "active",
        "sourceApp": "emailvoice",
        "emailVoiceLegacyId": str(contact.id),
        "externalKey": f"emailvoice:contact:{contact.workspace_id}:{contact.email}",
        "email": contact.email,
        "phone": contact.phone,
        "companyName": contact.company,
        "data": {
            "workspaceId": contact.workspace_id,
            "firstName": contact.first_name,
            "lastName": contact.last_name,
            "timezone": contact.timezone,
            "sourceChannel": contact.source_channel,
            "tags": list(contact.tags_json or []),
            "intents": list(contact.intent_json or []),
        },
        "createdAt": contact.created_at.isoformat(),
    }
    if parent_id is not None:
        payload["parentId"] = str(parent_id)
    _SHARED_RECORDS[str(contact.id)] = payload


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_account(
    session: Session,
    *,
    workspace_id: str = "ws-a",
    account_summary: str = "Analytical Health is evaluating cross-channel outreach.",
    suggested_next_action: str = "Reply with pricing clarity, then queue a call.",
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
    _register_shared_account(account)
    _register_shared_contact(ada, parent_id=account.id)
    _register_shared_contact(grace, parent_id=account.id)

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
        workspace_id=workspace_id,
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
        workspace_id=workspace_id,
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
                "account_summary": account_summary,
                "suggested_next_action": suggested_next_action,
            },
            email_draft="Subject: Analytical Health follow-up",
            voice_opener="Hi Ada, following up on pricing.",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    session.commit()
    session.refresh(account)
    session.refresh(ada)
    session.refresh(grace)
    return account, ada, grace


def _add_prospecting_snapshot(
    session: Session,
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
    account_summary: str,
    suggested_next_action: str,
    created_at: datetime,
) -> ProspectingSnapshot:
    snapshot = ProspectingSnapshot(
        workspace_id=workspace_id,
        contact_id=contact_id,
        company_url="https://analytical.example",
        sources_json=[{"label": "CRM contact", "summary": "Research source"}],
        research_json={
            "account_summary": account_summary,
            "suggested_next_action": suggested_next_action,
        },
        email_draft="Subject: Follow-up",
        voice_opener="Hi, following up.",
        created_at=created_at,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


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


def test_customer_360_excludes_cross_workspace_channel_rows() -> None:
    with _session() as session:
        account, ada, _grace = _seed_account(session)
        session.add(
            ChatbotConversation(
                workspace_id="ws-b",
                channel_type=ChatbotChannelType.whatsapp_business,
                visitor_id="foreign-visitor",
                contact_id=ada.id,
                status=ChatbotConversationStatus.escalated,
                escalated=True,
                escalation_reason="Foreign workspace escalation",
                last_message_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        _add_prospecting_snapshot(
            session,
            workspace_id="ws-b",
            contact_id=ada.id,
            account_summary="Foreign workspace research must not leak.",
            suggested_next_action="Do not use this cross-workspace action.",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        session.commit()

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)
        rows = list_customer_360_accounts(session, workspace_id="ws-a")

    assert profile is not None
    assert profile.channel_summaries["chatbot"].count == 1
    assert profile.channel_summaries["prospecting"].count == 1
    assert profile.prospecting_brief is not None
    assert (
        profile.prospecting_brief.account_summary
        == "Analytical Health is evaluating cross-channel outreach."
    )
    assert rows.data[0].channel_counts["chatbot"] == 1
    assert rows.data[0].channel_counts["prospecting"] == 1
    assert rows.data[0].top_next_action == "Reply with pricing clarity, then queue a call."
    assert "Foreign workspace research must not leak." not in {
        event.detail for event in profile.timeline
    }


def test_customer_360_excludes_cross_workspace_voice_and_email_rows() -> None:
    with _session() as session:
        account, ada, _grace = _seed_account(session)
        owner_id = uuid.uuid4()
        foreign_campaign = Campaign(
            name="Foreign Outreach",
            workspace_id="ws-b",
            created_by=owner_id,
        )
        session.add(foreign_campaign)
        session.flush()

        foreign_script = VoiceScript(
            campaign_id=foreign_campaign.id,
            name="Foreign Discovery",
            content="Foreign voice script.",
            created_by=owner_id,
        )
        session.add(foreign_script)
        session.flush()

        foreign_call_request = CallRequest(
            workspace_id="ws-b",
            contact_id=ada.id,
            campaign_id=foreign_campaign.id,
            voice_script_id=foreign_script.id,
            trigger_reason="foreign_workspace_call",
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        session.add(foreign_call_request)
        session.flush()
        session.add(
            CallSession(
                call_request_id=foreign_call_request.id,
                outcome=CallOutcome.answered,
                duration_seconds=44,
                transcript="FOREIGN WS-B transcript should not leak.",
                scheduling_interest=True,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=2),
            )
        )

        foreign_sequence = EmailSequence(
            campaign_id=foreign_campaign.id,
            name="Foreign Welcome",
            active=True,
            created_by=owner_id,
        )
        session.add(foreign_sequence)
        session.flush()
        foreign_state = ContactSequenceState(
            contact_id=ada.id,
            sequence_id=foreign_sequence.id,
        )
        session.add(foreign_state)
        session.flush()
        foreign_send = SendRequest(
            workspace_id="ws-b",
            contact_sequence_state_id=foreign_state.id,
            step_order=1,
            idempotency_key="ws-b-ada-foreign-step-1",
            status=SendRequestStatus.sent,
            sent_at=datetime.now(timezone.utc) - timedelta(minutes=4),
        )
        session.add(foreign_send)
        session.flush()
        session.add(
            EmailEvent(
                send_request_id=foreign_send.id,
                event_type="foreign_opened_marker",
                timestamp=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        session.commit()

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)
        rows = list_customer_360_accounts(session, workspace_id="ws-a")

    assert profile is not None
    assert profile.channel_summaries["voice"].count == 1
    assert profile.channel_summaries["email"].count == 1
    assert rows.data[0].channel_counts["voice"] == 1
    assert rows.data[0].channel_counts["email"] == 1
    timeline_text = {
        f"{event.event_type} {event.title} {event.detail}" for event in profile.timeline
    }
    assert not any("FOREIGN WS-B transcript" in item for item in timeline_text)
    assert not any("foreign_opened_marker" in item for item in timeline_text)


def test_profile_next_action_uses_prospecting_action_when_open_work_exists() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(
            session,
            suggested_next_action="Send a security packet, then invite procurement.",
        )

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile is not None
    assert profile.next_best_action is not None
    assert profile.next_best_action.title == "Send a security packet, then invite procurement"
    assert profile.next_best_action.source == "prospecting"
    assert profile.next_best_action.reason == "Prospecting research is ready."
    assert profile.next_best_action.priority == "medium"
    assert profile.next_best_action.title != "Reply with pricing clarity, then queue a call"


def test_chatbot_timeline_uses_latest_non_deleted_message() -> None:
    with _session() as session:
        account, ada, _grace = _seed_account(session)
        conversation = session.exec(
            select(ChatbotConversation).where(ChatbotConversation.contact_id == ada.id)
        ).one()
        conversation.escalation_reason = None
        older_content = "Older non-deleted chatbot message should be returned."
        session.add(
            ChatbotMessage(
                workspace_id="ws-a",
                conversation_id=conversation.id,
                direction=ChatbotMessageDirection.inbound,
                sender=ChatbotMessageSender.visitor,
                content=older_content,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
            )
        )
        session.add(
            ChatbotMessage(
                workspace_id="ws-a",
                conversation_id=conversation.id,
                direction=ChatbotMessageDirection.inbound,
                sender=ChatbotMessageSender.visitor,
                content="Deleted newest chatbot message should not be returned.",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=1),
                deleted_at=datetime.now(timezone.utc),
            )
        )
        session.commit()

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile is not None
    chatbot_event = next(event for event in profile.timeline if event.source == "chatbot")
    assert chatbot_event.detail == older_content


def test_timeline_voice_transcript_detail_is_bounded() -> None:
    with _session() as session:
        account, _ada, _grace = _seed_account(session)
        call_session = session.exec(select(CallSession)).one()
        long_transcript = (
            "LONG_TRANSCRIPT_START "
            + ("implementation pricing detail " * 20)
            + "RAW_TRANSCRIPT_END"
        )
        call_session.transcript = long_transcript
        session.add(call_session)
        session.commit()

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile is not None
    voice_event = next(event for event in profile.timeline if event.source == "voice")
    assert voice_event.detail != long_transcript
    assert len(voice_event.detail) <= 180
    assert "RAW_TRANSCRIPT_END" not in voice_event.detail


def test_prospecting_summary_and_actions_are_bounded() -> None:
    with _session() as session:
        long_summary = (
            "SUMMARY_START "
            + ("account research detail " * 25)
            + "SUMMARY_RAW_END"
        )
        long_action = (
            "ACTION_START "
            + ("coordinate executive follow-up " * 25)
            + "ACTION_RAW_END."
        )
        account, _ada, _grace = _seed_account(
            session,
            account_summary=long_summary,
            suggested_next_action=long_action,
        )

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)
        rows = list_customer_360_accounts(session, workspace_id="ws-a")

    assert profile is not None
    assert profile.prospecting_brief is not None
    assert profile.next_best_action is not None
    assert profile.prospecting_brief.account_summary != long_summary
    assert len(profile.prospecting_brief.account_summary) <= 180
    assert "SUMMARY_RAW_END" not in profile.prospecting_brief.account_summary
    prospecting_event = next(
        event
        for event in profile.timeline
        if event.source == "prospecting"
    )
    assert prospecting_event.detail != long_summary
    assert len(prospecting_event.detail) <= 180
    assert "SUMMARY_RAW_END" not in prospecting_event.detail
    assert profile.next_best_action.title != long_action.rstrip(".")
    assert len(profile.next_best_action.title) <= 180
    assert "ACTION_RAW_END" not in profile.next_best_action.title
    assert rows.data[0].top_next_action is not None
    assert rows.data[0].top_next_action != long_action
    assert len(rows.data[0].top_next_action) <= 180
    assert "ACTION_RAW_END" not in rows.data[0].top_next_action


def test_profile_timeline_includes_all_prospecting_snapshots() -> None:
    with _session() as session:
        account, ada, grace = _seed_account(session)
        ada_id = ada.id
        grace_id = grace.id
        _add_prospecting_snapshot(
            session,
            workspace_id="ws-a",
            contact_id=grace.id,
            account_summary="Grace confirmed procurement review.",
            suggested_next_action="Send Grace the implementation timeline.",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
        )
        session.commit()

        profile = get_account_profile(session, workspace_id="ws-a", account_id=account.id)

    assert profile is not None
    prospecting_events = [
        event
        for event in profile.timeline
        if event.source == "prospecting"
        and event.event_type == "prospecting_research"
    ]
    assert len(prospecting_events) == 2
    assert {event.contact_id for event in prospecting_events} == {ada_id, grace_id}
