"""Tests for app.workers.sequence_worker â€” full branch coverage.

Mocks SendGrid adapter, controls quiet hours, and exercises every branch in
``_process_batch``, ``_process_single``, ``_advance_step``, and helpers.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain_models import Campaign, CampaignStatus, Contact, GlobalControlState
from app.workers import sequence_worker

# ---------------------------------------------------------------------------
# Seed factories
# ---------------------------------------------------------------------------

def _seed_contact(session: Session, *, email: str = "lead@example.com",
                  first_name: str | None = "Ada") -> Contact:
    """Create and persist a Contact."""
    contact = Contact(
        workspace_id="ws-test",
        email=email,
        first_name=first_name,
        last_name="Lovelace",
        company="Analytical Engines",
    )
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def _seed_campaign(
    session: Session,
    *,
    workspace_id: str = "ws-test",
    status: CampaignStatus = CampaignStatus.active,
) -> Campaign:
    """Create and persist a Campaign."""
    campaign = Campaign(
        name="Worker Campaign",
        workspace_id=workspace_id,
        created_by=uuid.uuid4(),
        status=status,
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign


def _seed_sequence(
    session: Session,
    *,
    steps: int = 1,
    campaign_id: uuid.UUID | None = None,
) -> EmailSequence:
    """Create an EmailSequence and N steps starting at order=1."""
    seq = EmailSequence(
        campaign_id=campaign_id or uuid.uuid4(),
        name="welcome",
        created_by=uuid.uuid4(),
    )
    session.add(seq)
    session.commit()
    session.refresh(seq)
    for i in range(1, steps + 1):
        session.add(SequenceStep(
            sequence_id=seq.id,
            step_order=i,
            delay_days=1,
            subject_template=f"Hi {{{{first_name}}}} step {i}",
            body_template=f"<p>Body {i} for {{{{email}}}}</p>",
        ))
    session.commit()
    return seq


def _seed_state(
    session: Session,
    *,
    contact: Contact,
    sequence: EmailSequence,
    current_step: int = 1,
    next_send_at: datetime | None = None,
    status: SequenceStatus = SequenceStatus.active,
) -> ContactSequenceState:
    """Create a ContactSequenceState row."""
    state = ContactSequenceState(
        contact_id=contact.id,
        sequence_id=sequence.id,
        current_step=current_step,
        next_send_at=next_send_at or datetime.now(timezone.utc) - timedelta(minutes=1),
        status=status,
    )
    session.add(state)
    session.commit()
    session.refresh(state)
    return state


def _patch_engine(engine):
    """Patch the worker module's `engine` symbol with the in-memory engine."""
    return patch.object(sequence_worker, "engine", engine)


def _datetime_at(hour: int, minute: int = 0):
    """Build a MagicMock datetime module that returns a fixed UTC time."""
    fixed = datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = fixed
    return mock_dt


# ---------------------------------------------------------------------------
# _merge_tokens
# ---------------------------------------------------------------------------

def test_merge_tokens_replaces_allowed_fields() -> None:
    """Allowed tokens resolve to the contact's attribute value."""
    contact = Contact(workspace_id="ws", email="a@b.com", first_name="Ada")
    out = sequence_worker._merge_tokens("Hi {{first_name}} <{{email}}>", contact)
    assert out == "Hi Ada <a@b.com>"


def test_merge_tokens_blanks_unknown_field() -> None:
    """Tokens not in ALLOWED_TOKENS render as empty string."""
    contact = Contact(workspace_id="ws", email="a@b.com")
    assert sequence_worker._merge_tokens("X{{secret}}Y", contact) == "XY"


def test_merge_tokens_blanks_none_value() -> None:
    """An allowed token whose value is None resolves to empty string."""
    contact = Contact(workspace_id="ws", email="a@b.com", first_name=None)
    assert sequence_worker._merge_tokens("[{{first_name}}]", contact) == "[]"


# ---------------------------------------------------------------------------
# _is_quiet_hours
# ---------------------------------------------------------------------------

def test_is_quiet_hours_true_late_evening() -> None:
    """22:00 UTC is inside the 21:00-08:00 window."""
    with patch.object(sequence_worker, "datetime", _datetime_at(22)):
        assert sequence_worker._is_quiet_hours() is True


def test_is_quiet_hours_true_early_morning() -> None:
    """02:00 UTC is inside the overnight quiet window."""
    with patch.object(sequence_worker, "datetime", _datetime_at(2)):
        assert sequence_worker._is_quiet_hours() is True


def test_is_quiet_hours_false_midday() -> None:
    """12:00 UTC is outside the quiet window."""
    with patch.object(sequence_worker, "datetime", _datetime_at(12)):
        assert sequence_worker._is_quiet_hours() is False


def test_is_quiet_hours_non_overnight_window() -> None:
    """Cover the else-branch when start < end."""
    with patch.object(sequence_worker, "QUIET_HOURS_START", time(9, 0)), \
         patch.object(sequence_worker, "QUIET_HOURS_END", time(17, 0)), \
         patch.object(sequence_worker, "datetime", _datetime_at(12)):
        assert sequence_worker._is_quiet_hours() is True
    with patch.object(sequence_worker, "QUIET_HOURS_START", time(9, 0)), \
         patch.object(sequence_worker, "QUIET_HOURS_END", time(17, 0)), \
         patch.object(sequence_worker, "datetime", _datetime_at(8)):
        assert sequence_worker._is_quiet_hours() is False


# ---------------------------------------------------------------------------
# _daily_send_count / _is_suppressed
# ---------------------------------------------------------------------------

def test_daily_send_count_returns_zero_for_empty(memory_session: Session) -> None:
    """No SendRequests -> 0."""
    assert sequence_worker._daily_send_count(memory_session) == 0


def test_daily_send_count_excludes_failed(memory_session: Session) -> None:
    """Failed sends are excluded from the daily count."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    memory_session.add(SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key="ok",
        status=SendRequestStatus.sent,
    ))
    memory_session.add(SendRequest(
        contact_sequence_state_id=state.id,
        step_order=2,
        idempotency_key="bad",
        status=SendRequestStatus.failed,
    ))
    memory_session.commit()
    assert sequence_worker._daily_send_count(memory_session) == 1


def test_is_suppressed_true_when_email_listed(memory_session: Session) -> None:
    """An email with a suppression row returns True."""
    memory_session.add(EmailSuppression(email="block@example.com", reason="bounce"))
    memory_session.commit()
    assert sequence_worker._is_suppressed(memory_session, "block@example.com") is True


def test_is_suppressed_false_when_email_unknown(memory_session: Session) -> None:
    """No suppression row -> False."""
    assert sequence_worker._is_suppressed(memory_session, "ok@example.com") is False


# ---------------------------------------------------------------------------
# _process_batch
# ---------------------------------------------------------------------------

def test_process_batch_skips_during_quiet_hours(memory_session: Session) -> None:
    """Quiet hours -> 0, no adapter constructed."""
    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=True), \
         patch.object(sequence_worker, "SendGridAdapter") as adapter_cls:
        result = asyncio.run(sequence_worker._process_batch())
    assert result == 0
    adapter_cls.assert_not_called()


def test_process_batch_returns_zero_when_daily_cap_reached(memory_session: Session) -> None:
    """Daily cap reached -> bail out."""
    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=False), \
         patch.object(sequence_worker, "_daily_send_count",
                      return_value=sequence_worker.DEFAULT_DAILY_CAP), \
         patch.object(sequence_worker, "SendGridAdapter"):
        result = asyncio.run(sequence_worker._process_batch())
    assert result == 0


def test_process_batch_returns_zero_when_no_due(memory_session: Session) -> None:
    """No due states -> 0."""
    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=False), \
         patch.object(sequence_worker, "SendGridAdapter"):
        result = asyncio.run(sequence_worker._process_batch())
    assert result == 0


def test_process_batch_processes_due_state_successfully(memory_session: Session) -> None:
    """A due ContactSequenceState gets processed and the count returned."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=2)
    _seed_state(memory_session, contact=contact, sequence=seq)

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"message_id": "MSG1", "status_code": 202})

    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=False), \
         patch.object(sequence_worker, "SendGridAdapter", return_value=adapter):
        processed = asyncio.run(sequence_worker._process_batch())

    assert processed == 1
    adapter.send_email.assert_awaited_once()


def test_process_batch_skips_when_global_pause_active(memory_session: Session) -> None:
    """Global pause prevents the launched sequence worker from sending."""
    contact = _seed_contact(memory_session)
    campaign = _seed_campaign(memory_session, workspace_id=contact.workspace_id)
    seq = _seed_sequence(memory_session, steps=1, campaign_id=campaign.id)
    _seed_state(memory_session, contact=contact, sequence=seq)
    memory_session.add(GlobalControlState(workspace_id=contact.workspace_id, paused=True))
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"message_id": "MSG1", "status_code": 202})

    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=False), \
         patch.object(sequence_worker, "SendGridAdapter", return_value=adapter):
        processed = asyncio.run(sequence_worker._process_batch())

    assert processed == 0
    adapter.send_email.assert_not_awaited()


def test_process_batch_handles_exception_and_breaks(memory_session: Session) -> None:
    """An unexpected exception in `_process_single` triggers rollback + break."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=1)
    _seed_state(memory_session, contact=contact, sequence=seq)

    with _patch_engine(memory_session.bind), \
         patch.object(sequence_worker, "_is_quiet_hours", return_value=False), \
         patch.object(sequence_worker, "SendGridAdapter"), \
         patch.object(sequence_worker, "_process_single",
                      side_effect=RuntimeError("boom")):
        processed = asyncio.run(sequence_worker._process_batch())
    assert processed == 0


# ---------------------------------------------------------------------------
# _process_single â€” branch coverage
# ---------------------------------------------------------------------------

def test_process_single_stops_when_contact_missing(memory_session: Session) -> None:
    """Missing Contact -> sequence state moves to stopped."""
    seq = _seed_sequence(memory_session)
    state = ContactSequenceState(
        contact_id=uuid.uuid4(),  # not present
        sequence_id=seq.id,
        current_step=1,
        next_send_at=datetime.now(timezone.utc),
    )
    memory_session.add(state)
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.status == SequenceStatus.stopped
    adapter.send_email.assert_not_called()


def test_process_single_stops_when_contact_suppressed(memory_session: Session) -> None:
    """Suppressed email -> stopped + signal_type=suppressed."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    memory_session.add(EmailSuppression(email=contact.email, reason="bounce"))
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.status == SequenceStatus.stopped
    assert state.signal_type == "suppressed"
    adapter.send_email.assert_not_called()


def test_process_single_completes_when_no_step_found(memory_session: Session) -> None:
    """No matching SequenceStep -> sequence completed."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=1)
    state = _seed_state(memory_session, contact=contact, sequence=seq, current_step=99)

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.status == SequenceStatus.completed
    adapter.send_email.assert_not_called()


def test_process_single_advances_when_existing_send_already_sent(memory_session: Session) -> None:
    """An existing sent SendRequest -> advance to next step without sending."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=2)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    idem = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"
    memory_session.add(SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=idem,
        status=SendRequestStatus.sent,
    ))
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.current_step == 2
    adapter.send_email.assert_not_called()


def test_process_single_stops_when_max_retries_exceeded(memory_session: Session) -> None:
    """Existing failed SendRequest with retry_count >= len(RETRY_DELAYS) -> stopped."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    idem = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"
    memory_session.add(SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=idem,
        status=SendRequestStatus.failed,
        retry_count=len(sequence_worker.RETRY_DELAYS),
    ))
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.status == SequenceStatus.stopped
    assert state.signal_type == "send_failed"
    adapter.send_email.assert_not_called()


def test_process_single_skips_when_retry_window_open(memory_session: Session) -> None:
    """Failed SendRequest still inside its retry window -> no send, no state change."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    idem = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"
    sr = SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=idem,
        status=SendRequestStatus.failed,
        retry_count=0,
    )
    memory_session.add(sr)
    memory_session.commit()
    memory_session.refresh(sr)

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    # SQLite drops tzinfo; force the worker's datetime.now() to return a naive
    # value so the retry-window comparison doesn't blow up on tz-mixing.
    naive_dt = MagicMock(wraps=datetime)
    naive_dt.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
    with patch.object(sequence_worker, "datetime", naive_dt):
        with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    assert state.status == SequenceStatus.active
    adapter.send_email.assert_not_called()


def test_process_single_does_not_resend_stale_pending_unknown_outcome(
    memory_session: Session,
) -> None:
    """A stale pending SendRequest may already have reached the provider."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    idem = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"
    old_sr = SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=idem,
        status=SendRequestStatus.pending,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    memory_session.add(old_sr)
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"message_id": "DUP", "status_code": 202})
    naive_dt = MagicMock(wraps=datetime)
    naive_dt.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
    with patch.object(sequence_worker, "datetime", naive_dt):
        with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    memory_session.refresh(old_sr)
    assert old_sr.status == SendRequestStatus.pending
    assert state.status == SequenceStatus.active
    adapter.send_email.assert_not_called()


def test_process_single_sends_and_advances_on_success(memory_session: Session) -> None:
    """Successful send -> SendRequest sent, state advances to next step."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=2)
    state = _seed_state(memory_session, contact=contact, sequence=seq)

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"message_id": "MID", "status_code": 202})
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    sr = memory_session.exec(select(SendRequest)).first()
    assert sr is not None and sr.status == SendRequestStatus.sent
    assert sr.provider_message_id == "MID"
    assert state.current_step == 2


def test_process_single_persists_send_request_before_provider_call(
    memory_session: Session,
) -> None:
    """The SendRequest intent is committed before awaiting the email provider."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=2)
    state = _seed_state(memory_session, contact=contact, sequence=seq)

    async def _send_email(**_kwargs: object) -> dict[str, object]:
        sr = memory_session.exec(select(SendRequest)).first()
        assert sr is not None
        assert sr.status == SendRequestStatus.pending
        return {"message_id": "MID", "status_code": 202}

    adapter = MagicMock()
    adapter.send_email = AsyncMock(side_effect=_send_email)

    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
        asyncio.run(sequence_worker._process_single(memory_session, state))

    sr = memory_session.exec(select(SendRequest)).first()
    assert sr is not None
    assert sr.status == SendRequestStatus.sent


def test_process_single_marks_failed_on_send_error(memory_session: Session) -> None:
    """Adapter returns no message_id -> SendRequest failed, retry_count +1."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 500, "error": "boom"})
    with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    sr = memory_session.exec(select(SendRequest)).first()
    assert sr is not None and sr.status == SendRequestStatus.failed
    assert sr.retry_count == 1


def test_process_single_retries_after_window_elapses(memory_session: Session) -> None:
    """Failed SendRequest past its retry window is retried (and increments)."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    idem = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"
    old_sr = SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=idem,
        status=SendRequestStatus.failed,
        retry_count=0,
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    memory_session.add(old_sr)
    memory_session.commit()

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"message_id": "MID2", "status_code": 202})
    # SQLite drops tzinfo; force naive `datetime.now()` so the worker's
    # tz-aware comparison against the round-tripped created_at works.
    naive_dt = MagicMock(wraps=datetime)
    naive_dt.now.return_value = datetime.now(timezone.utc).replace(tzinfo=None)
    with patch.object(sequence_worker, "datetime", naive_dt):
        with patch.object(sequence_worker, "resolve_email_adapter", return_value=adapter):
            asyncio.run(sequence_worker._process_single(memory_session, state))
    memory_session.commit()

    memory_session.refresh(old_sr)
    assert old_sr.status == SendRequestStatus.sent


# ---------------------------------------------------------------------------
# _advance_step
# ---------------------------------------------------------------------------

def test_advance_step_moves_to_next_step(memory_session: Session) -> None:
    """When a next step exists, current_step increments and next_send_at is scheduled."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=2)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    current = memory_session.exec(
        select(SequenceStep).where(SequenceStep.step_order == 1)
    ).first()
    sequence_worker._advance_step(memory_session, state, current)
    memory_session.commit()

    assert state.current_step == 2
    assert state.next_send_at is not None
    assert state.status == SequenceStatus.active


def test_advance_step_completes_when_no_more_steps(memory_session: Session) -> None:
    """Final step -> sequence completed and next_send_at cleared."""
    contact = _seed_contact(memory_session)
    seq = _seed_sequence(memory_session, steps=1)
    state = _seed_state(memory_session, contact=contact, sequence=seq)
    current = memory_session.exec(
        select(SequenceStep).where(SequenceStep.step_order == 1)
    ).first()
    sequence_worker._advance_step(memory_session, state, current)
    memory_session.commit()

    assert state.status == SequenceStatus.completed
    assert state.next_send_at is None


# ---------------------------------------------------------------------------
# run_worker / main
# ---------------------------------------------------------------------------

def test_run_worker_processes_handles_exception_then_cancels() -> None:
    """run_worker dispatches batches, recovers from exceptions, then exits."""
    counter = {"n": 0}

    async def fake_batch():
        counter["n"] += 1
        if counter["n"] == 1:
            return 3
        raise RuntimeError("boom")

    async def fake_sleep(_seconds):
        if counter["n"] >= 2:
            raise asyncio.CancelledError()

    with patch.object(sequence_worker, "_process_batch", side_effect=fake_batch), \
            patch.object(sequence_worker, "record_worker_heartbeat"), \
         patch.object(sequence_worker.asyncio, "sleep", side_effect=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(sequence_worker.run_worker())

    assert counter["n"] >= 2


def test_main_invokes_asyncio_run() -> None:
    """`main` configures logging and dispatches `run_worker` via asyncio.run."""
    sentinel = object()
    run_worker_mock = MagicMock(return_value=sentinel)
    with patch.object(sequence_worker.asyncio, "run") as run_mock, \
         patch.object(sequence_worker.logging, "basicConfig") as basic_config, \
         patch.object(sequence_worker, "run_worker", run_worker_mock):
        sequence_worker.main()
    basic_config.assert_called_once()
    run_worker_mock.assert_called_once_with()
    run_mock.assert_called_once_with(sentinel)
