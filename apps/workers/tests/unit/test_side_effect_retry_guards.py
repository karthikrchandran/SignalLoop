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
from app.domain_models import Campaign, CampaignStatus, Contact
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
