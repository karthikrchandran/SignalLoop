"""Tests for ``app.workers.postcall_worker``.

Covers all branches of the polling worker:
- no pending sessions
- answered call Ã¢â€ â€™ summary sent
- answered call missing CallRequest (early return)
- answered call missing Contact (uses defaults)
- non-answered call Ã¢â€ â€™ skipped
- exception during processing Ã¢â€ â€™ status set to "error"
- TEAM_NOTIFICATION_EMAIL unset Ã¢â€ â€™ skip send
- ``run_worker`` loop iterates and handles per-iteration errors
- ``main`` boots logging and runs the worker
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.shared_records import service as shared_record_service
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import Campaign, Contact, OutboxEvent
from app.workers import postcall_worker

_SHARED_CONTACTS: dict[object, object] = {}


def _run(coro):
    return asyncio.run(coro)


def _build_session_mock(pending):
    """Construct a Session mock whose ``exec(...).all()`` returns ``pending``."""
    session = MagicMock()
    session.__enter__.return_value = session
    session.__exit__.return_value = None

    exec_result = MagicMock()
    exec_result.all.return_value = pending
    session.exec.return_value = exec_result
    return session


def _build_call_session(outcome=CallOutcome.answered, sid=1, request_id=10):
    cs = MagicMock()
    cs.id = sid
    cs.outcome = outcome
    cs.call_request_id = request_id
    cs.postcall_status = None
    return cs


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


@pytest.fixture(autouse=True)
def _shared_contact_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    _SHARED_CONTACTS.clear()

    def get_shared_contact(*, workspace_id: str, contact_id):  # noqa: ANN001, ARG001
        return _SHARED_CONTACTS.get(contact_id)

    monkeypatch.setattr(shared_record_service, "get_shared_contact", get_shared_contact)


def _seed_answered_call(session: Session, *, workspace_id: str = "ws") -> CallSession:
    owner_id = uuid.uuid4()
    campaign = Campaign(
        name="Campaign",
        workspace_id=workspace_id,
        created_by=owner_id,
    )
    session.add(campaign)
    session.flush()

    contact = Contact(
        workspace_id=workspace_id,
        email="caller@example.com",
        first_name="Casey",
        last_name="Call",
        company="ExampleCo",
        phone="+15551234567",
    )
    session.add(contact)
    session.flush()
    _SHARED_CONTACTS[contact.id] = contact

    script = VoiceScript(
        campaign_id=campaign.id,
        name="Script",
        content="Say hello.",
        created_by=owner_id,
    )
    session.add(script)
    session.flush()

    call_request = CallRequest(
        workspace_id=campaign.workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual",
        scheduled_at=datetime.now(timezone.utc),
    )
    session.add(call_request)
    session.flush()

    call_session = CallSession(
        call_request_id=call_request.id,
        twilio_call_sid="CA123",
        outcome=CallOutcome.answered,
        transcript="Interested in a follow-up.",
    )
    session.add(call_session)
    session.commit()
    session.refresh(call_session)
    return call_session


class _CapturingSummaryAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sent: list[dict] = []

    async def send_email(self, **kwargs):
        key = kwargs["idempotency_key"]
        intent = self.session.exec(
            select(OutboxEvent).where(OutboxEvent.idempotency_key == key)
        ).first()
        assert intent is not None
        assert intent.published_at is None
        self.sent.append(kwargs)
        return {"status_code": 202, "message_id": "summary-1"}


# ---------------------------------------------------------------------------
# _process_completed_calls
# ---------------------------------------------------------------------------


def test_process_completed_calls_returns_zero_when_no_pending() -> None:
    """No pending sessions Ã¢â€¡â€™ returns 0 and never instantiates the adapter."""
    session = _build_session_mock(pending=[])

    with (
        patch("app.workers.postcall_worker.Session", return_value=session),
        patch("app.workers.postcall_worker.SendGridAdapter") as adapter_cls,
    ):
        count = _run(postcall_worker._process_completed_calls())

    assert count == 0
    adapter_cls.assert_not_called()
    session.commit.assert_not_called()


def test_process_completed_calls_sends_summary_for_answered_call() -> None:
    """An answered call gets a summary email and ``postcall_status='summary_sent'``."""
    cs = _build_call_session(outcome=CallOutcome.answered)
    session = _build_session_mock(pending=[cs])

    adapter_instance = MagicMock()
    adapter_instance.send_email = AsyncMock()

    with (
        patch("app.workers.postcall_worker.Session", return_value=session),
        patch(
            "app.workers.postcall_worker.SendGridAdapter",
            return_value=adapter_instance,
        ),
        patch(
            "app.workers.postcall_worker._send_summary", new_callable=AsyncMock
        ) as send_summary,
    ):
        count = _run(postcall_worker._process_completed_calls())

    assert count == 1
    assert cs.postcall_status == "summary_sent"
    send_summary.assert_awaited_once_with(session, cs)
    session.add.assert_called_with(cs)
    session.commit.assert_called_once()


def test_process_completed_calls_skips_non_answered_outcome() -> None:
    """Non-answered outcomes get ``postcall_status='skipped'`` (no summary call)."""
    non_answered = next(o for o in CallOutcome if o != CallOutcome.answered)
    cs = _build_call_session(outcome=non_answered)
    session = _build_session_mock(pending=[cs])

    with (
        patch("app.workers.postcall_worker.Session", return_value=session),
        patch("app.workers.postcall_worker.SendGridAdapter"),
        patch(
            "app.workers.postcall_worker._send_summary", new_callable=AsyncMock
        ) as send_summary,
    ):
        count = _run(postcall_worker._process_completed_calls())

    assert count == 1
    assert cs.postcall_status == "skipped"
    send_summary.assert_not_awaited()


def test_process_completed_calls_sets_error_status_on_exception() -> None:
    """If ``_send_summary`` raises, status becomes 'error' and loop continues."""
    cs = _build_call_session(outcome=CallOutcome.answered)
    session = _build_session_mock(pending=[cs])

    with (
        patch("app.workers.postcall_worker.Session", return_value=session),
        patch("app.workers.postcall_worker.SendGridAdapter"),
        patch(
            "app.workers.postcall_worker._send_summary",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
    ):
        count = _run(postcall_worker._process_completed_calls())

    # ``processed`` is incremented inside the try-block *after* _send_summary;
    # an exception means it stays at 0, but the call_session still gets persisted
    # with status="error".
    assert count == 0
    assert cs.postcall_status == "error"
    session.add.assert_called_with(cs)
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# _send_summary
# ---------------------------------------------------------------------------


def test_send_summary_returns_early_when_call_request_missing() -> None:
    """Missing ``CallRequest`` short-circuits before generating a summary."""
    session = MagicMock()
    session.get.return_value = None  # CallRequest not found
    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 202, "message_id": "summary-1"})
    cs = _build_call_session()

    with patch("app.workers.postcall_worker.generate_summary") as gen, \
         patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter):
        _run(postcall_worker._send_summary(session, cs))

    gen.assert_not_called()
    adapter.send_email.assert_not_awaited()


def test_send_summary_uses_contact_defaults_when_contact_missing() -> None:
    """When contact lookup returns None, defaults ('Unknown'/empty) are used."""
    session = MagicMock()
    call_request = MagicMock(
        workspace_id="ws-stored",
        contact_id=99,
        shared_contact_id=99,
        campaign_id=uuid.uuid4(),
    )
    session.get.side_effect = [call_request, None]

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 202, "message_id": "summary-1"})
    cs = _build_call_session()

    summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")
    shared_contact_lookup = MagicMock(return_value=None)

    with (
        patch(
            "app.workers.postcall_worker.generate_summary", return_value=summary
        ) as gen,
        patch.object(
            postcall_worker,
            "resolve_team_notification_email",
            return_value="ops@x.io",
        ),
        patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
        patch.object(
            postcall_worker.shared_record_service,
            "get_shared_contact",
            shared_contact_lookup,
        ),
        patch.object(
            postcall_worker,
            "_prepare_postcall_summary_intent",
            return_value=SimpleNamespace(id=uuid.uuid4(), idempotency_key="postcall:1:summary_email"),
        ),
        patch.object(postcall_worker, "mark_outbox_published"),
    ):
        _run(postcall_worker._send_summary(session, cs))

    _, kwargs = gen.call_args
    assert kwargs["contact_name"] == "Unknown"
    assert kwargs["contact_company"] == ""
    assert kwargs["contact_email"] == ""
    shared_contact_lookup.assert_called_once_with(
        workspace_id="ws-stored",
        contact_id=99,
    )
    adapter.send_email.assert_awaited_once_with(
        to="ops@x.io",
        subject="s",
        body_html="<p/>",
        body_text="t",
        idempotency_key="postcall:1:summary_email",
    )


def test_send_summary_uses_contact_fields_when_present() -> None:
    """Contact's name/company/email are forwarded to the summary generator."""
    session = MagicMock()
    contact = MagicMock(
        first_name="Ada",
        last_name="Lovelace",
        company="Analytical",
        email="a@l.io",
        workspace_id="ws-a",
    )
    call_request = MagicMock(
        workspace_id="ws-a",
        contact_id=1,
        shared_contact_id=1,
        campaign_id=uuid.uuid4(),
    )
    session.get.side_effect = [call_request, None]
    _SHARED_CONTACTS[1] = contact

    adapter = MagicMock()
    adapter.send_email = AsyncMock(return_value={"status_code": 202, "message_id": "summary-1"})
    cs = _build_call_session()
    summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")

    with (
        patch(
            "app.workers.postcall_worker.generate_summary", return_value=summary
        ) as gen,
        patch.object(
            postcall_worker,
            "resolve_team_notification_email",
            return_value="ops@x.io",
        ),
        patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
        patch.object(
            postcall_worker,
            "_prepare_postcall_summary_intent",
            return_value=SimpleNamespace(id=uuid.uuid4(), idempotency_key="postcall:1:summary_email"),
        ),
        patch.object(postcall_worker, "mark_outbox_published"),
    ):
        _run(postcall_worker._send_summary(session, cs))

    _, kwargs = gen.call_args
    assert kwargs["contact_name"] == "Ada Lovelace"
    assert kwargs["contact_company"] == "Analytical"
    assert kwargs["contact_email"] == "a@l.io"
    adapter.send_email.assert_awaited_once_with(
        to="ops@x.io",
        subject="s",
        body_html="<p/>",
        body_text="t",
        idempotency_key="postcall:1:summary_email",
    )


def test_send_summary_uses_shared_contact_when_local_row_is_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session() as session:
        call_session = _seed_answered_call(session, workspace_id="ws-shared")
        call_request = session.get(CallRequest, call_session.call_request_id)
        assert call_request is not None
        shared_contact_id = call_request.shared_contact_id

        monkeypatch.setattr(
            postcall_worker.shared_record_service,
            "get_shared_contact",
            lambda **kwargs: Contact(
                id=shared_contact_id,
                workspace_id="ws-shared",
                email="shared@example.com",
                first_name="Shared",
                last_name="Buyer",
                company="Shared Co",
                phone="+15551234567",
            ),
        )

        adapter = MagicMock()
        adapter.send_email = AsyncMock(
            return_value={"status_code": 202, "message_id": "summary-1"}
        )
        summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")

        with (
            patch(
                "app.workers.postcall_worker.generate_summary",
                return_value=summary,
            ) as gen,
            patch.object(
                postcall_worker,
                "resolve_team_notification_email",
                return_value="ops@example.com",
            ),
            patch.object(
                postcall_worker,
                "resolve_email_adapter",
                return_value=adapter,
            ),
        ):
            _run(postcall_worker._send_summary(session, call_session))

        _, kwargs = gen.call_args
        assert kwargs["contact_name"] == "Shared Buyer"
        assert kwargs["contact_company"] == "Shared Co"
        assert kwargs["contact_email"] == "shared@example.com"


def test_send_summary_uses_outbox_intent_and_skips_duplicate() -> None:
    with _session() as session:
        call_session = _seed_answered_call(session)
        adapter = _CapturingSummaryAdapter(session)
        summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")

        with (
            patch("app.workers.postcall_worker.generate_summary", return_value=summary),
            patch.object(
                postcall_worker,
                "resolve_team_notification_email",
                return_value="ops@example.com",
            ),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
        ):
            _run(postcall_worker._send_summary(session, call_session))
            _run(postcall_worker._send_summary(session, call_session))

        outbox = session.exec(select(OutboxEvent)).all()

    expected_key = f"postcall:{call_session.id}:summary_email"
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["to"] == "ops@example.com"
    assert adapter.sent[0]["idempotency_key"] == expected_key
    assert [event.idempotency_key for event in outbox] == [expected_key]
    assert outbox[0].published_at is not None


def test_send_summary_rejects_unpublished_intent_without_resend() -> None:
    with _session() as session:
        call_session = _seed_answered_call(session)
        session.add(
            OutboxEvent(
                aggregate_id=call_session.id,
                aggregate_type="call_session",
                event_type="postcall.summary_email_requested",
                event_data={"to": "ops@example.com"},
                idempotency_key=f"postcall:{call_session.id}:summary_email",
            )
        )
        session.commit()
        adapter = _CapturingSummaryAdapter(session)

        with (
            patch("app.workers.postcall_worker.generate_summary", return_value=MagicMock()),
            patch.object(
                postcall_worker,
                "resolve_team_notification_email",
                return_value="ops@example.com",
            ),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
            pytest.raises(RuntimeError, match="already in progress"),
        ):
            _run(postcall_worker._send_summary(session, call_session))

        outbox = session.exec(select(OutboxEvent)).all()

    assert adapter.sent == []
    assert len(outbox) == 1
    assert outbox[0].published_at is None


def test_send_summary_rejection_leaves_intent_unpublished() -> None:
    with _session() as session:
        call_session = _seed_answered_call(session)
        adapter = MagicMock()
        adapter.send_email = AsyncMock(return_value={"status_code": 500, "message_id": ""})

        with (
            patch("app.workers.postcall_worker.generate_summary", return_value=MagicMock()),
            patch.object(
                postcall_worker,
                "resolve_team_notification_email",
                return_value="ops@example.com",
            ),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
            pytest.raises(RuntimeError, match="rejected"),
        ):
            _run(postcall_worker._send_summary(session, call_session))

        outbox = session.exec(select(OutboxEvent)).all()

    adapter.send_email.assert_awaited_once()
    assert len(outbox) == 1
    assert outbox[0].published_at is None


def test_send_summary_skips_send_when_team_email_unset() -> None:
    """No ``TEAM_NOTIFICATION_EMAIL`` configured Ã¢â€¡â€™ generator runs but no email is sent."""
    session = MagicMock()
    call_request = MagicMock(
        workspace_id="ws-a",
        contact_id=1,
        shared_contact_id=1,
        campaign_id=uuid.uuid4(),
    )
    contact = MagicMock(
        first_name="X",
        last_name="Y",
        company="C",
        email="e@e.io",
        workspace_id="ws-a",
    )
    session.get.side_effect = [call_request, None]
    _SHARED_CONTACTS[1] = contact

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    cs = _build_call_session()

    with (
        patch("app.workers.postcall_worker.generate_summary", return_value=MagicMock()),
        patch.object(
            postcall_worker,
            "resolve_team_notification_email",
            return_value="",
        ),
        patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
    ):
        _run(postcall_worker._send_summary(session, cs))

    adapter.send_email.assert_not_awaited()


# ---------------------------------------------------------------------------
# run_worker / main
# ---------------------------------------------------------------------------


def test_run_worker_iterates_and_handles_processed_count() -> None:
    """The worker loops, logs processed counts, and stops on CancelledError."""
    call_counts = [2, 0]

    async def fake_process():
        if not call_counts:
            raise asyncio.CancelledError()
        return call_counts.pop(0)

    async def fake_sleep(_secs):
        if not call_counts:
            raise asyncio.CancelledError()

    with (
        patch(
            "app.workers.postcall_worker._process_completed_calls",
            side_effect=fake_process,
        ),
        patch("app.workers.postcall_worker.record_worker_heartbeat"),
        patch("app.workers.postcall_worker.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            _run(postcall_worker.run_worker())


def test_run_worker_swallows_loop_iteration_errors() -> None:
    """Exceptions inside ``_process_completed_calls`` are logged, not raised."""
    iteration = {"n": 0}

    async def fake_process():
        iteration["n"] += 1
        if iteration["n"] == 1:
            raise RuntimeError("kaboom")
        raise asyncio.CancelledError()

    async def fake_sleep(_secs):
        return None

    with (
        patch(
            "app.workers.postcall_worker._process_completed_calls",
            side_effect=fake_process,
        ),
        patch("app.workers.postcall_worker.record_worker_heartbeat"),
        patch("app.workers.postcall_worker.asyncio.sleep", side_effect=fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            _run(postcall_worker.run_worker())

    assert iteration["n"] == 2  # first raised, second cancelled


def test_main_configures_logging_and_runs_worker() -> None:
    """``main`` configures logging and dispatches ``run_worker`` via ``asyncio.run``."""
    sentinel = object()
    run_worker_mock = MagicMock(return_value=sentinel)

    with (
        patch("app.workers.postcall_worker.logging.basicConfig") as basic_cfg,
        patch("app.workers.postcall_worker.asyncio.run") as run_mock,
        patch("app.workers.postcall_worker.run_worker", run_worker_mock),
    ):
        postcall_worker.main()

        basic_cfg.assert_called_once()
        run_worker_mock.assert_called_once_with()
        run_mock.assert_called_once_with(sentinel)
