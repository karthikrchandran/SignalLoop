from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlmodel import Session, SQLModel, create_engine

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain.voice.models import (
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import Campaign, CampaignStatus, Contact, GlobalControlState
from worker_app import call_worker, sequence_worker  # type: ignore[import-untyped]


def _run(coro):
    return asyncio.run(coro)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_campaign(session: Session) -> Campaign:
    campaign = Campaign(
        name="Campaign",
        workspace_id="ws-test",
        status=CampaignStatus.active,
        created_by=uuid.uuid4(),
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def _seed_contact(session: Session) -> Contact:
    contact = Contact(
        workspace_id="ws-test",
        email="lead@example.com",
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical Engines",
        phone="+15551234567",
        consent_email=True,
        consent_voice=True,
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def _seed_sequence_state(
    session: Session, *, contact: Contact, campaign: Campaign
) -> ContactSequenceState:
    sequence = EmailSequence(
        campaign_id=campaign.id,
        name="Sequence",
        status=SequenceStatus.active,
        created_by=uuid.uuid4(),
    )
    session.add(sequence)
    session.flush()
    session.add(
        SequenceStep(
            sequence_id=sequence.id,
            step_order=1,
            subject_template="Hello {{first_name}}",
            body_template="<p>Hello {{first_name}}</p>",
            delay_days=0,
        )
    )
    session.flush()
    state = ContactSequenceState(
        contact_id=contact.id,
        sequence_id=sequence.id,
        status=SequenceStatus.active,
        current_step=1,
        next_send_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def _seed_call_request(
    session: Session, *, contact: Contact, campaign: Campaign
) -> CallRequest:
    script = VoiceScript(
        campaign_id=campaign.id,
        name="Script",
        content="Say hello.",
        created_by=uuid.uuid4(),
    )
    session.add(script)
    session.flush()
    request = CallRequest(
        workspace_id=campaign.workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual_queue",
        status=CallRequestStatus.queued,
        scheduled_at=datetime.now(timezone.utc),
    )
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def test_sequence_worker_does_not_resend_stale_pending_unknown_outcome() -> None:
    with _session() as session:
        campaign = _seed_campaign(session)
        contact = _seed_contact(session)
        state = _seed_sequence_state(session, contact=contact, campaign=campaign)
        key = f"{state.id}:{state.current_step}"
        send_request = SendRequest(
            workspace_id=campaign.workspace_id,
            contact_sequence_state_id=state.id,
            step_order=1,
            idempotency_key=key,
            status=SendRequestStatus.pending,
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(send_request)
        session.commit()

        adapter = MagicMock()
        adapter.send_email = AsyncMock(return_value={"status_code": 202, "message_id": "dup"})
        naive_dt = MagicMock(wraps=datetime)
        naive_dt.now.return_value = datetime.now(UTC).replace(tzinfo=None)
        with (
            patch.object(sequence_worker, "datetime", naive_dt),
            patch.object(sequence_worker, "_in_quiet_hours", return_value=False),
        ):
            _run(
                sequence_worker._process_single(
                    session,
                    state,
                    workspace_id="ws-test",
                    campaign_id=campaign.id,
                    adapter=adapter,
                )
            )
        session.commit()
        session.refresh(send_request)
        session.refresh(state)

    assert send_request.status == SendRequestStatus.pending
    assert state.status == SequenceStatus.active
    adapter.send_email.assert_not_called()


def test_sequence_worker_does_not_apply_another_workspaces_suppression() -> None:
    with _session() as session:
        campaign = _seed_campaign(session)
        contact = _seed_contact(session)
        state = _seed_sequence_state(session, contact=contact, campaign=campaign)
        session.add(
            EmailSuppression(
                workspace_id="workspace-a",
                email=contact.email,
                reason="unsubscribe",
            )
        )
        session.commit()

        adapter = MagicMock()
        adapter.send_email = AsyncMock(
            return_value={"status_code": 202, "message_id": "message-b"}
        )
        with patch.object(sequence_worker, "_in_quiet_hours", return_value=False):
            _run(
                sequence_worker._process_single(
                    session,
                    state,
                    workspace_id=contact.workspace_id,
                    campaign_id=campaign.id,
                    adapter=adapter,
                )
            )

    adapter.send_email.assert_awaited_once()


def test_sequence_worker_rejects_cross_workspace_contact_before_send() -> None:
    with _session() as session:
        campaign = _seed_campaign(session)
        contact = _seed_contact(session)
        contact.workspace_id = "workspace-b"
        session.add(contact)
        session.commit()
        state = _seed_sequence_state(session, contact=contact, campaign=campaign)
        adapter = MagicMock()
        adapter.send_email = AsyncMock(
            return_value={"status_code": 202, "message_id": "cross-tenant"}
        )

        with patch.object(sequence_worker, "_in_quiet_hours", return_value=False):
            _run(
                sequence_worker._process_single(
                    session,
                    state,
                    workspace_id=campaign.workspace_id,
                    campaign_id=campaign.id,
                    adapter=adapter,
                )
            )
        session.commit()
        session.refresh(state)

    assert state.status == SequenceStatus.stopped
    assert state.signal_type == "workspace_mismatch"
    adapter.send_email.assert_not_awaited()


def test_sequence_worker_denies_missing_email_consent_before_send() -> None:
    with _session() as session:
        campaign = _seed_campaign(session)
        contact = _seed_contact(session)
        contact.consent_email = False
        session.add(contact)
        session.commit()
        state = _seed_sequence_state(session, contact=contact, campaign=campaign)
        adapter = MagicMock()
        adapter.send_email = AsyncMock(
            return_value={"status_code": 202, "message_id": "must-not-send"}
        )

        with patch.object(sequence_worker, "_in_quiet_hours", return_value=False):
            _run(
                sequence_worker._process_single(
                    session,
                    state,
                    workspace_id=campaign.workspace_id,
                    campaign_id=campaign.id,
                    adapter=adapter,
                )
            )
        session.commit()
        session.refresh(state)

    assert state.status == SequenceStatus.stopped
    assert state.signal_type == "CONSENT_MISSING"
    adapter.send_email.assert_not_awaited()


def test_sequence_batch_continues_past_paused_workspace() -> None:
    with _session() as session:
        engine = session.get_bind()
        paused_campaign = _seed_campaign(session)
        paused_campaign.workspace_id = "workspace-a"
        paused_contact = _seed_contact(session)
        paused_contact.workspace_id = "workspace-a"
        paused_state = _seed_sequence_state(
            session, contact=paused_contact, campaign=paused_campaign
        )
        paused_state.next_send_at = datetime.now(UTC) - timedelta(minutes=2)

        active_campaign = _seed_campaign(session)
        active_campaign.workspace_id = "workspace-b"
        active_contact = _seed_contact(session)
        active_contact.workspace_id = "workspace-b"
        active_contact.email = "active@example.com"
        active_state = _seed_sequence_state(
            session, contact=active_contact, campaign=active_campaign
        )
        session.add(GlobalControlState(workspace_id="workspace-a", paused=True))
        session.add(paused_campaign)
        session.add(paused_contact)
        session.add(paused_state)
        session.add(active_campaign)
        session.add(active_contact)
        session.add(active_state)
        session.commit()
        active_state_id = active_state.id

    adapter = MagicMock()
    adapter.send_email = AsyncMock(
        return_value={"status_code": 202, "message_id": "workspace-b-send"}
    )
    with (
        patch.object(sequence_worker, "engine", engine),
        patch.object(sequence_worker, "_in_quiet_hours", return_value=False),
        patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter),
    ):
        processed = _run(sequence_worker.process_batch())

    with Session(engine) as session:
        active_state = session.get(ContactSequenceState, active_state_id)
        assert active_state is not None
        assert active_state.status == SequenceStatus.completed
    assert processed == 1
    adapter.send_email.assert_awaited_once()


def test_call_worker_does_not_redial_stale_initiating_unknown_outcome() -> None:
    with _session() as session:
        campaign = _seed_campaign(session)
        contact = _seed_contact(session)
        request = _seed_call_request(session, contact=contact, campaign=campaign)
        call_session = CallSession(
            call_request_id=request.id,
            twilio_call_sid="",
            twilio_status="initiating",
            twilio_status_updated_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        session.add(call_session)
        session.commit()

        adapter = MagicMock()
        adapter._account_sid = "ACtest"
        adapter.initiate_call = AsyncMock(return_value={"call_sid": "CAdup"})
        with patch.object(call_worker, "_is_within_call_hours", return_value=True):
            result = _run(
                call_worker._initiate_one(
                    session,
                    request,
                    workspace_id="ws-test",
                    adapter=adapter,
                )
            )
        session.commit()
        session.refresh(request)
        session.refresh(call_session)

    assert result is False
    assert request.status == CallRequestStatus.in_progress
    assert call_session.twilio_status == "initiating"
    assert call_session.twilio_call_sid == ""
    adapter.initiate_call.assert_not_awaited()
