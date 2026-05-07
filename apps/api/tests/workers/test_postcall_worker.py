"""Tests for ``app.workers.postcall_worker``.

Covers all branches of the polling worker:
- no pending sessions
- answered call → summary sent
- answered call missing CallRequest (early return)
- answered call missing Contact (uses defaults)
- non-answered call → skipped
- exception during processing → status set to "error"
- TEAM_NOTIFICATION_EMAIL unset → skip send
- ``run_worker`` loop iterates and handles per-iteration errors
- ``main`` boots logging and runs the worker
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.voice.models import CallOutcome
from app.workers import postcall_worker


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


# ---------------------------------------------------------------------------
# _process_completed_calls
# ---------------------------------------------------------------------------


def test_process_completed_calls_returns_zero_when_no_pending() -> None:
    """No pending sessions ⇒ returns 0 and never instantiates the adapter."""
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
    send_summary.assert_awaited_once_with(session, adapter_instance, cs)
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
    adapter.send_email = AsyncMock()
    cs = _build_call_session()

    with patch("app.workers.postcall_worker.generate_summary") as gen:
        _run(postcall_worker._send_summary(session, adapter, cs))

    gen.assert_not_called()
    adapter.send_email.assert_not_awaited()


def test_send_summary_uses_contact_defaults_when_contact_missing() -> None:
    """When contact lookup returns None, defaults ('Unknown'/empty) are used."""
    session = MagicMock()
    call_request = MagicMock(contact_id=99)
    # First .get -> CallRequest, second .get -> Contact
    session.get.side_effect = [call_request, None]

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    cs = _build_call_session()

    summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")

    with (
        patch(
            "app.workers.postcall_worker.generate_summary", return_value=summary
        ) as gen,
        patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", "ops@x.io"),
    ):
        _run(postcall_worker._send_summary(session, adapter, cs))

    _, kwargs = gen.call_args
    assert kwargs["contact_name"] == "Unknown"
    assert kwargs["contact_company"] == ""
    assert kwargs["contact_email"] == ""
    adapter.send_email.assert_awaited_once_with(
        to="ops@x.io", subject="s", body_html="<p/>", body_text="t"
    )


def test_send_summary_uses_contact_fields_when_present() -> None:
    """Contact's name/company/email are forwarded to the summary generator."""
    session = MagicMock()
    contact = MagicMock(
        first_name="Ada", last_name="Lovelace", company="Analytical", email="a@l.io"
    )
    call_request = MagicMock(contact_id=1)
    session.get.side_effect = [call_request, contact]

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    cs = _build_call_session()
    summary = MagicMock(subject="s", html_body="<p/>", transcript_preview="t")

    with (
        patch(
            "app.workers.postcall_worker.generate_summary", return_value=summary
        ) as gen,
        patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", "ops@x.io"),
    ):
        _run(postcall_worker._send_summary(session, adapter, cs))

    _, kwargs = gen.call_args
    assert kwargs["contact_name"] == "Ada Lovelace"
    assert kwargs["contact_company"] == "Analytical"
    assert kwargs["contact_email"] == "a@l.io"


def test_send_summary_skips_send_when_team_email_unset() -> None:
    """No ``TEAM_NOTIFICATION_EMAIL`` configured ⇒ generator runs but no email is sent."""
    session = MagicMock()
    call_request = MagicMock(contact_id=1)
    contact = MagicMock(first_name="X", last_name="Y", company="C", email="e@e.io")
    session.get.side_effect = [call_request, contact]

    adapter = MagicMock()
    adapter.send_email = AsyncMock()
    cs = _build_call_session()

    with (
        patch("app.workers.postcall_worker.generate_summary", return_value=MagicMock()),
        patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", ""),
    ):
        _run(postcall_worker._send_summary(session, adapter, cs))

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
