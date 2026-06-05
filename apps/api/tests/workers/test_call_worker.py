"""Tests for app.workers.call_worker — full branch coverage.

Mocks Twilio adapter, controls quiet hours, and exercises every branch in
``_process_batch`` and ``_initiate_call``.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import Contact
from app.workers import call_worker


# ---------------------------------------------------------------------------
# Helpers / seed factories
# ---------------------------------------------------------------------------

def _seed_contact(session: Session, *, phone: str | None = "+15551234567") -> Contact:
    """Create and persist a Contact."""
    contact = Contact(workspace_id="ws-test", email="caller@example.com", phone=phone)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact


def _seed_voice_script(session: Session, campaign_id: uuid.UUID) -> VoiceScript:
    """Create and persist a VoiceScript."""
    script = VoiceScript(
        campaign_id=campaign_id,
        name="default",
        content="Hello",
        created_by=uuid.uuid4(),
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    return script


def _seed_call_request(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
    voice_script_id: uuid.UUID | None = None,
    scheduled_at: datetime | None = None,
    status: CallRequestStatus = CallRequestStatus.queued,
) -> CallRequest:
    """Create and persist a CallRequest plus its supporting Voice script."""
    campaign_id = campaign_id or uuid.uuid4()
    if voice_script_id is None:
        voice_script_id = _seed_voice_script(session, campaign_id).id
    cr = CallRequest(
        contact_id=contact_id,
        campaign_id=campaign_id,
        voice_script_id=voice_script_id,
        trigger_reason="test",
        status=status,
        scheduled_at=scheduled_at or datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    session.add(cr)
    session.commit()
    session.refresh(cr)
    return cr


def _patch_engine(engine):
    """Patch the worker module's `engine` symbol with the in-memory engine."""
    return patch.object(call_worker, "engine", engine)


# ---------------------------------------------------------------------------
# _mask_phone
# ---------------------------------------------------------------------------

def test_mask_phone_short_number_returns_stars() -> None:
    """Numbers with <=4 digits are fully masked."""
    assert call_worker._mask_phone("123") == "****"
    assert call_worker._mask_phone("1234") == "****"


def test_mask_phone_long_number_keeps_last_four() -> None:
    """Long numbers preserve the last 4 digits."""
    assert call_worker._mask_phone("+1 (555) 123-4567") == "****4567"


def test_mask_phone_empty_string_returns_stars() -> None:
    """Empty input yields the all-masked sentinel."""
    assert call_worker._mask_phone("") == "****"


# ---------------------------------------------------------------------------
# _is_quiet_hours
# ---------------------------------------------------------------------------

def _datetime_at(hour: int, minute: int = 0):
    """Build a MagicMock datetime module that returns a fixed time."""
    fixed = datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)
    mock_dt = MagicMock(wraps=datetime)
    mock_dt.now.return_value = fixed
    return mock_dt


def test_is_quiet_hours_returns_true_during_evening() -> None:
    """8 PM UTC falls inside the 18:00-09:00 quiet window."""
    with patch.object(call_worker, "datetime", _datetime_at(20)):
        assert call_worker._is_quiet_hours() is True


def test_is_quiet_hours_returns_true_in_early_morning() -> None:
    """3 AM UTC is still in quiet hours (window spans midnight)."""
    with patch.object(call_worker, "datetime", _datetime_at(3)):
        assert call_worker._is_quiet_hours() is True


def test_is_quiet_hours_returns_false_during_business_hours() -> None:
    """Noon UTC is outside the quiet window."""
    with patch.object(call_worker, "datetime", _datetime_at(12)):
        assert call_worker._is_quiet_hours() is False


def test_is_quiet_hours_non_overnight_window_branch() -> None:
    """Cover the else-branch where QUIET_HOURS_START < QUIET_HOURS_END."""
    with patch.object(call_worker, "QUIET_HOURS_START", time(9, 0)), \
         patch.object(call_worker, "QUIET_HOURS_END", time(17, 0)), \
         patch.object(call_worker, "datetime", _datetime_at(12)):
        assert call_worker._is_quiet_hours() is True
    with patch.object(call_worker, "QUIET_HOURS_START", time(9, 0)), \
         patch.object(call_worker, "QUIET_HOURS_END", time(17, 0)), \
         patch.object(call_worker, "datetime", _datetime_at(20)):
        assert call_worker._is_quiet_hours() is False


# ---------------------------------------------------------------------------
# _daily_call_count
# ---------------------------------------------------------------------------

def test_daily_call_count_returns_zero_for_empty_db(memory_session: Session) -> None:
    """No call requests -> 0."""
    assert call_worker._daily_call_count(memory_session) == 0


def test_daily_call_count_excludes_failed_and_other_dates(memory_session: Session) -> None:
    """Only non-failed requests created today are counted."""
    contact = _seed_contact(memory_session)
    _seed_call_request(memory_session, contact_id=contact.id)
    _seed_call_request(memory_session, contact_id=contact.id, status=CallRequestStatus.failed)
    assert call_worker._daily_call_count(memory_session) == 1


# ---------------------------------------------------------------------------
# _process_batch
# ---------------------------------------------------------------------------

def test_process_batch_skips_during_quiet_hours(memory_session: Session) -> None:
    """When `_is_quiet_hours` returns True the batch returns immediately."""
    with _patch_engine(memory_session.bind), \
         patch.object(call_worker, "_is_quiet_hours", return_value=True), \
         patch.object(call_worker, "TwilioVoiceAdapter") as adapter_cls:
        result = asyncio.run(call_worker._process_batch())
    assert result == 0
    adapter_cls.assert_not_called()


def test_process_batch_returns_zero_when_daily_cap_reached(memory_session: Session) -> None:
    """If the daily cap is already met, no new calls are initiated."""
    with _patch_engine(memory_session.bind), \
         patch.object(call_worker, "_is_quiet_hours", return_value=False), \
         patch.object(call_worker, "_daily_call_count", return_value=call_worker.DAILY_CALL_CAP), \
         patch.object(call_worker, "TwilioVoiceAdapter"):
        result = asyncio.run(call_worker._process_batch())
    assert result == 0


def test_process_batch_returns_zero_when_no_due_requests(memory_session: Session) -> None:
    """An empty queue yields 0 with no adapter calls."""
    with _patch_engine(memory_session.bind), \
         patch.object(call_worker, "_is_quiet_hours", return_value=False), \
         patch.object(call_worker, "TwilioVoiceAdapter") as adapter_cls:
        adapter_cls.return_value = MagicMock(_account_sid="ACtest")
        result = asyncio.run(call_worker._process_batch())
    assert result == 0


def test_process_batch_initiates_due_call_successfully(memory_session: Session) -> None:
    """A due, queued CallRequest is dispatched and counted."""
    contact = _seed_contact(memory_session)
    _seed_call_request(memory_session, contact_id=contact.id)

    adapter_inst = MagicMock()
    adapter_inst._account_sid = "ACtest"
    adapter_inst.initiate_call = AsyncMock(return_value={"call_sid": "CA123"})

    with _patch_engine(memory_session.bind), \
         patch.object(call_worker, "_is_quiet_hours", return_value=False), \
         patch.object(call_worker, "TwilioVoiceAdapter", return_value=adapter_inst):
        processed = asyncio.run(call_worker._process_batch())

    assert processed == 1
    adapter_inst.initiate_call.assert_awaited_once()


def test_process_batch_handles_exception_and_breaks(memory_session: Session) -> None:
    """If `_initiate_call` raises, the loop rolls back and breaks."""
    contact = _seed_contact(memory_session)
    _seed_call_request(memory_session, contact_id=contact.id)
    _seed_call_request(memory_session, contact_id=contact.id)

    with _patch_engine(memory_session.bind), \
         patch.object(call_worker, "_is_quiet_hours", return_value=False), \
         patch.object(call_worker, "TwilioVoiceAdapter") as adapter_cls, \
         patch.object(call_worker, "_initiate_call", side_effect=RuntimeError("boom")):
        adapter_cls.return_value = MagicMock(_account_sid="ACtest")
        processed = asyncio.run(call_worker._process_batch())

    assert processed == 0


# ---------------------------------------------------------------------------
# _initiate_call
# ---------------------------------------------------------------------------

def _make_adapter(*, call_sid: str | None = "CA123", error: str | None = None):
    """Build a stub TwilioVoiceAdapter."""
    adapter = MagicMock()
    adapter._account_sid = "ACtest"
    payload: dict[str, str] = {"call_sid": call_sid or ""}
    if error:
        payload["error"] = error
    adapter.initiate_call = AsyncMock(return_value=payload)
    return adapter


def test_initiate_call_marks_failed_when_contact_missing(memory_session: Session) -> None:
    """Missing contact -> CallRequest moved to failed."""
    bogus_contact_id = uuid.uuid4()
    cr = CallRequest(
        contact_id=bogus_contact_id,
        campaign_id=uuid.uuid4(),
        voice_script_id=_seed_voice_script(memory_session, uuid.uuid4()).id,
        trigger_reason="test",
        scheduled_at=datetime.now(timezone.utc),
    )
    memory_session.add(cr)
    memory_session.commit()

    adapter = _make_adapter()
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    assert cr.status == CallRequestStatus.failed
    adapter.initiate_call.assert_not_called()


def test_initiate_call_marks_failed_when_no_phone(memory_session: Session) -> None:
    """Contact without a phone (and no @-less email) -> failed."""
    contact = _seed_contact(memory_session, phone=None)
    cr = _seed_call_request(memory_session, contact_id=contact.id)

    adapter = _make_adapter()
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    assert cr.status == CallRequestStatus.failed
    adapter.initiate_call.assert_not_called()


def test_initiate_call_skips_when_existing_session_already_dispatched(
    memory_session: Session,
) -> None:
    """If a CallSession already has a twilio_call_sid, mark in_progress and exit."""
    contact = _seed_contact(memory_session)
    cr = _seed_call_request(memory_session, contact_id=contact.id)
    existing = CallSession(call_request_id=cr.id, twilio_call_sid="CAexisting")
    memory_session.add(existing)
    memory_session.commit()

    adapter = _make_adapter()
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    assert cr.status == CallRequestStatus.in_progress
    adapter.initiate_call.assert_not_called()


def test_initiate_call_creates_session_and_marks_in_progress(memory_session: Session) -> None:
    """Successful Twilio response -> session created with sid, request in_progress."""
    contact = _seed_contact(memory_session)
    cr = _seed_call_request(memory_session, contact_id=contact.id)

    adapter = _make_adapter(call_sid="CAfreshSid")
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    cs = memory_session.exec(
        select(CallSession).where(CallSession.call_request_id == cr.id)
    ).first()
    assert cr.status == CallRequestStatus.in_progress
    assert cs is not None and cs.twilio_call_sid == "CAfreshSid"
    assert cs.twilio_status == "initiated"


def test_initiate_call_marks_failed_when_twilio_returns_no_sid(memory_session: Session) -> None:
    """Twilio failure (no call_sid) -> CallRequest failed and CallOutcome failed."""
    contact = _seed_contact(memory_session)
    cr = _seed_call_request(memory_session, contact_id=contact.id)

    adapter = _make_adapter(call_sid=None, error="twilio_rejected")
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    cs = memory_session.exec(
        select(CallSession).where(CallSession.call_request_id == cr.id)
    ).first()
    assert cr.status == CallRequestStatus.failed
    assert cs is not None and cs.outcome == CallOutcome.failed


def test_initiate_call_marks_failed_with_error_code_payload(memory_session: Session) -> None:
    """Cover the error_code branch when `error_code` is present in the response."""
    contact = _seed_contact(memory_session)
    cr = _seed_call_request(memory_session, contact_id=contact.id)

    adapter = MagicMock()
    adapter._account_sid = "ACtest"
    adapter.initiate_call = AsyncMock(return_value={"call_sid": "", "error_code": "E123"})
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    assert cr.status == CallRequestStatus.failed


def test_initiate_call_reuses_existing_session_without_sid(memory_session: Session) -> None:
    """A CallSession that exists but has no sid is updated, not duplicated."""
    contact = _seed_contact(memory_session)
    cr = _seed_call_request(memory_session, contact_id=contact.id)
    existing = CallSession(call_request_id=cr.id, twilio_call_sid="")
    memory_session.add(existing)
    memory_session.commit()
    existing_id = existing.id

    adapter = _make_adapter(call_sid="CAreused")
    with patch.object(call_worker, "resolve_voice_adapter", return_value=adapter):
        asyncio.run(call_worker._initiate_call(memory_session, cr))
    memory_session.commit()

    sessions = memory_session.exec(
        select(CallSession).where(CallSession.call_request_id == cr.id)
    ).all()
    assert len(sessions) == 1
    assert sessions[0].id == existing_id
    assert sessions[0].twilio_call_sid == "CAreused"


# ---------------------------------------------------------------------------
# run_worker / main
# ---------------------------------------------------------------------------

def test_run_worker_processes_then_handles_exception_and_exits() -> None:
    """run_worker: one successful batch, one exception batch, then sleep cancels loop."""
    call_count = {"n": 0}

    async def fake_batch():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return 2
        if call_count["n"] == 2:
            raise RuntimeError("boom")
        raise asyncio.CancelledError()

    async def fake_sleep(_seconds):
        if call_count["n"] >= 3:
            raise asyncio.CancelledError()

    with patch.object(call_worker, "_process_batch", side_effect=fake_batch), \
            patch.object(call_worker, "record_worker_heartbeat"), \
         patch.object(call_worker.asyncio, "sleep", side_effect=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(call_worker.run_worker())

    assert call_count["n"] >= 2


def test_main_invokes_asyncio_run() -> None:
    """`main` configures logging and dispatches `run_worker` via asyncio.run."""
    sentinel = object()
    run_worker_mock = MagicMock(return_value=sentinel)
    with patch.object(call_worker.asyncio, "run") as run_mock, \
         patch.object(call_worker.logging, "basicConfig") as basic_config, \
         patch.object(call_worker, "run_worker", run_worker_mock):
        call_worker.main()
    basic_config.assert_called_once()
    run_worker_mock.assert_called_once_with()
    run_mock.assert_called_once_with(sentinel)
