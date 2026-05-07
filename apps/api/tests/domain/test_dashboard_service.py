"""Unit tests for ``app.domain.dashboard.service``."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.dashboard.service import (
    get_call_metrics,
    get_daily_cap_status,
    get_email_metrics,
    get_signal_summary,
)
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.signals.models import SignalEvent
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import Campaign, Contact
from app.workers.call_worker import DAILY_CALL_CAP
from app.workers.sequence_worker import DEFAULT_DAILY_CAP as EMAIL_DAILY_CAP


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """In-memory SQLite session per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _make_campaign(session: Session, workspace_id: str = "ws") -> Campaign:
    camp = Campaign(name="C", created_by=uuid.uuid4(), workspace_id=workspace_id)
    session.add(camp)
    session.commit()
    session.refresh(camp)
    return camp


def _make_sequence(session: Session, campaign_id: uuid.UUID) -> EmailSequence:
    seq = EmailSequence(campaign_id=campaign_id, name="S", created_by=uuid.uuid4())
    session.add(seq)
    session.commit()
    session.refresh(seq)
    return seq


def _make_contact(session: Session) -> Contact:
    c = Contact(workspace_id="ws", email=f"{uuid.uuid4()}@x.com")
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _make_state(
    session: Session, contact_id: uuid.UUID, sequence_id: uuid.UUID, status: SequenceStatus
) -> ContactSequenceState:
    state = ContactSequenceState(
        contact_id=contact_id, sequence_id=sequence_id, current_step=1, status=status
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def _make_send(
    session: Session, state_id: uuid.UUID, status: SendRequestStatus, idem: str
) -> SendRequest:
    sr = SendRequest(
        contact_sequence_state_id=state_id,
        step_order=1,
        idempotency_key=idem,
        status=status,
    )
    session.add(sr)
    session.commit()
    session.refresh(sr)
    return sr


# ---------- get_email_metrics ----------


def test_get_email_metrics_no_sequences_returns_zeroes(session: Session) -> None:
    """Campaign with no sequences returns zero metrics."""
    metrics = get_email_metrics(session, uuid.uuid4())
    assert metrics == {
        "total_enrolled": 0,
        "active": 0,
        "completed": 0,
        "stopped": 0,
        "sent": 0,
        "failed": 0,
    }


def test_get_email_metrics_aggregates_states_and_sends(session: Session) -> None:
    """States and send counts are correctly aggregated."""
    camp = _make_campaign(session)
    seq = _make_sequence(session, camp.id)
    c1 = _make_contact(session)
    c2 = _make_contact(session)
    c3 = _make_contact(session)
    s1 = _make_state(session, c1.id, seq.id, SequenceStatus.active)
    s2 = _make_state(session, c2.id, seq.id, SequenceStatus.completed)
    _make_state(session, c3.id, seq.id, SequenceStatus.stopped)
    _make_send(session, s1.id, SendRequestStatus.sent, "k1")
    _make_send(session, s1.id, SendRequestStatus.sent, "k2")
    _make_send(session, s2.id, SendRequestStatus.failed, "k3")

    metrics = get_email_metrics(session, camp.id)
    assert metrics["total_enrolled"] == 3
    assert metrics["active"] == 1
    assert metrics["completed"] == 1
    assert metrics["stopped"] == 1
    assert metrics["sent"] == 2
    assert metrics["failed"] == 1


# ---------- get_call_metrics ----------


def _make_voice_script(session: Session, campaign_id: uuid.UUID) -> VoiceScript:
    vs = VoiceScript(
        campaign_id=campaign_id, name="vs", content="x", created_by=uuid.uuid4()
    )
    session.add(vs)
    session.commit()
    session.refresh(vs)
    return vs


def _make_call_request(
    session: Session,
    campaign_id: uuid.UUID,
    contact_id: uuid.UUID,
    voice_script_id: uuid.UUID,
    status: CallRequestStatus,
) -> CallRequest:
    cr = CallRequest(
        contact_id=contact_id,
        campaign_id=campaign_id,
        voice_script_id=voice_script_id,
        trigger_reason="test",
        scheduled_at=datetime.now(timezone.utc),
        status=status,
    )
    session.add(cr)
    session.commit()
    session.refresh(cr)
    return cr


def test_get_call_metrics_aggregates_statuses_and_outcomes(session: Session) -> None:
    """Combines call statuses and call session outcomes."""
    camp = _make_campaign(session)
    contact = _make_contact(session)
    vs = _make_voice_script(session, camp.id)

    cr_q = _make_call_request(session, camp.id, contact.id, vs.id, CallRequestStatus.queued)
    cr_p = _make_call_request(session, camp.id, contact.id, vs.id, CallRequestStatus.in_progress)
    cr_c = _make_call_request(session, camp.id, contact.id, vs.id, CallRequestStatus.completed)
    cr_f = _make_call_request(session, camp.id, contact.id, vs.id, CallRequestStatus.failed)

    session.add(CallSession(call_request_id=cr_c.id, twilio_call_sid="sid1", outcome=CallOutcome.answered))
    session.add(CallSession(call_request_id=cr_p.id, twilio_call_sid="sid2", outcome=CallOutcome.voicemail))
    session.add(CallSession(call_request_id=cr_q.id, twilio_call_sid="sid3", outcome=CallOutcome.no_answer))
    session.add(CallSession(call_request_id=cr_f.id, twilio_call_sid="sid4", outcome=CallOutcome.no_answer))
    session.commit()

    metrics = get_call_metrics(session, camp.id)
    assert metrics["total_queued"] == 1
    assert metrics["in_progress"] == 1
    assert metrics["completed"] == 1
    assert metrics["failed"] == 1
    assert metrics["answered"] == 1
    assert metrics["voicemail"] == 1
    assert metrics["no_answer"] == 2


def test_get_call_metrics_empty(session: Session) -> None:
    """No calls yields zeroed metrics."""
    metrics = get_call_metrics(session, uuid.uuid4())
    assert metrics == {
        "total_queued": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
        "answered": 0,
        "voicemail": 0,
        "no_answer": 0,
    }


# ---------- get_signal_summary ----------


def test_get_signal_summary_groups_counts(session: Session) -> None:
    """Counts grouped by channel and signal_type."""
    camp = _make_campaign(session)
    contact = _make_contact(session)
    for _ in range(2):
        session.add(SignalEvent(
            contact_id=contact.id, campaign_id=camp.id,
            channel="email", signal_type="reply",
        ))
    session.add(SignalEvent(
        contact_id=contact.id, campaign_id=camp.id,
        channel="voice", signal_type="answered",
    ))
    session.commit()

    summary = get_signal_summary(session, camp.id)
    assert summary == {"email": {"reply": 2}, "voice": {"answered": 1}}


def test_get_signal_summary_empty(session: Session) -> None:
    """No signals returns empty dict."""
    assert get_signal_summary(session, uuid.uuid4()) == {}


# ---------- get_daily_cap_status ----------


def test_get_daily_cap_status_counts_today_only(session: Session) -> None:
    """Yesterday's sends/calls are excluded from today's counts."""
    camp = _make_campaign(session, workspace_id="ws-a")
    seq = _make_sequence(session, camp.id)
    contact = _make_contact(session)
    state = _make_state(session, contact.id, seq.id, SequenceStatus.active)

    today = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)

    sent_today = SendRequest(
        contact_sequence_state_id=state.id, step_order=1,
        idempotency_key="t1", status=SendRequestStatus.sent,
    )
    sent_today.created_at = today
    session.add(sent_today)

    sent_yesterday = SendRequest(
        contact_sequence_state_id=state.id, step_order=1,
        idempotency_key="y1", status=SendRequestStatus.sent,
    )
    sent_yesterday.created_at = yesterday
    session.add(sent_yesterday)

    pending_today = SendRequest(
        contact_sequence_state_id=state.id, step_order=1,
        idempotency_key="p1", status=SendRequestStatus.pending,
    )
    pending_today.created_at = today
    session.add(pending_today)

    vs = _make_voice_script(session, camp.id)
    call_today = CallRequest(
        contact_id=contact.id, campaign_id=camp.id, voice_script_id=vs.id,
        trigger_reason="t", scheduled_at=today, status=CallRequestStatus.completed,
    )
    call_today.created_at = today
    session.add(call_today)

    call_in_progress = CallRequest(
        contact_id=contact.id, campaign_id=camp.id, voice_script_id=vs.id,
        trigger_reason="t", scheduled_at=today, status=CallRequestStatus.in_progress,
    )
    call_in_progress.created_at = today
    session.add(call_in_progress)

    call_yesterday = CallRequest(
        contact_id=contact.id, campaign_id=camp.id, voice_script_id=vs.id,
        trigger_reason="t", scheduled_at=yesterday, status=CallRequestStatus.completed,
    )
    call_yesterday.created_at = yesterday
    session.add(call_yesterday)

    queued_call = CallRequest(
        contact_id=contact.id, campaign_id=camp.id, voice_script_id=vs.id,
        trigger_reason="t", scheduled_at=today, status=CallRequestStatus.queued,
    )
    queued_call.created_at = today
    session.add(queued_call)

    session.commit()

    status = get_daily_cap_status(session, workspace_id="ws-a")
    assert status["email_sent_today"] == 1
    assert status["email_daily_cap"] == EMAIL_DAILY_CAP
    assert status["call_initiated_today"] == 2
    assert status["call_daily_cap"] == DAILY_CALL_CAP


def test_get_daily_cap_status_filters_by_workspace(session: Session) -> None:
    """Other workspaces are excluded."""
    camp_a = _make_campaign(session, workspace_id="ws-a")
    camp_b = _make_campaign(session, workspace_id="ws-b")
    seq_a = _make_sequence(session, camp_a.id)
    seq_b = _make_sequence(session, camp_b.id)
    c_a = _make_contact(session)
    c_b = _make_contact(session)
    state_a = _make_state(session, c_a.id, seq_a.id, SequenceStatus.active)
    state_b = _make_state(session, c_b.id, seq_b.id, SequenceStatus.active)
    today = datetime.now(timezone.utc).replace(hour=12)

    for state in (state_a, state_b):
        sr = SendRequest(
            contact_sequence_state_id=state.id, step_order=1,
            idempotency_key=f"k-{state.id}", status=SendRequestStatus.sent,
        )
        sr.created_at = today
        session.add(sr)
    session.commit()

    status = get_daily_cap_status(session, workspace_id="ws-a")
    assert status["email_sent_today"] == 1
    assert status["call_initiated_today"] == 0


def test_get_daily_cap_status_empty(session: Session) -> None:
    """No data -> zero counts but cap constants still returned."""
    status = get_daily_cap_status(session, workspace_id="ws-empty")
    assert status["email_sent_today"] == 0
    assert status["call_initiated_today"] == 0
    assert status["email_daily_cap"] == EMAIL_DAILY_CAP
    assert status["call_daily_cap"] == DAILY_CALL_CAP
