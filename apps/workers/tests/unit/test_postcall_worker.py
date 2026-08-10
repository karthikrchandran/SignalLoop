from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
    VoiceScript,
)
from app.domain_models import Campaign, Contact, OutboxEvent
from worker_app import postcall_worker  # type: ignore[import-untyped]


def _run(coro):
    return asyncio.run(coro)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_completed_call(session: Session) -> tuple[CallRequest, CallSession]:
    owner_id = uuid.uuid4()
    campaign = Campaign(name="Campaign", workspace_id="ws", created_by=owner_id)
    session.add(campaign)
    session.flush()

    contact = Contact(
        workspace_id="ws",
        email="caller@example.com",
        first_name="Casey",
        last_name="Call",
        company="ExampleCo",
        phone="+15551234567",
    )
    session.add(contact)
    session.flush()

    script = VoiceScript(
        campaign_id=campaign.id,
        name="Script",
        content="Say hello.",
        created_by=owner_id,
    )
    session.add(script)
    session.flush()

    request = CallRequest(
        workspace_id=campaign.workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual",
        status=CallRequestStatus.completed,
        scheduled_at=datetime.now(timezone.utc),
    )
    session.add(request)
    session.flush()

    call_session = CallSession(
        call_request_id=request.id,
        twilio_call_sid="CA123",
        outcome=CallOutcome.answered,
        transcript="Interested in a follow-up.",
    )
    session.add(call_session)
    session.commit()
    session.refresh(request)
    session.refresh(call_session)
    return request, call_session


class _CapturingAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sent: list[dict] = []

    async def send_email(self, **kwargs):
        intent = self.session.exec(
            select(OutboxEvent).where(
                OutboxEvent.idempotency_key == kwargs["idempotency_key"]
            )
        ).first()
        assert intent is not None
        assert intent.published_at is None
        self.sent.append(kwargs)
        return {"status_code": 202, "message_id": "summary-1"}


def test_build_summary_uses_stored_workspace_without_campaign() -> None:
    with _session() as session:
        request, call_session = _seed_completed_call(session)

        summary = postcall_worker._build_summary(
            request,
            call_session,
            contact=None,
            campaign=None,
        )

    assert summary["workspace_id"] == request.workspace_id


def test_process_session_uses_outbox_intent_before_send() -> None:
    with _session() as session:
        request, call_session = _seed_completed_call(session)
        adapter = _CapturingAdapter(session)

        with (
            patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", "ops@example.com"),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
        ):
            _run(postcall_worker._process_session(session, request, call_session))

        outbox = session.exec(select(OutboxEvent)).all()
        audits = session.exec(select(AuditEvent)).all()

    expected_key = f"postcall:{call_session.id}:summary_email"
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["idempotency_key"] == expected_key
    assert [event.idempotency_key for event in outbox] == [expected_key]
    assert outbox[0].published_at is not None
    assert call_session.post_call_processed is True
    assert audits[-1].payload["summary_email_sent"] is True


def test_process_session_rejects_unpublished_intent_without_resend() -> None:
    with _session() as session:
        request, call_session = _seed_completed_call(session)
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
        adapter = _CapturingAdapter(session)

        with (
            patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", "ops@example.com"),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
            pytest.raises(RuntimeError, match="already in progress"),
        ):
            _run(postcall_worker._process_session(session, request, call_session))

        outbox = session.exec(select(OutboxEvent)).all()

    assert adapter.sent == []
    assert outbox[0].published_at is None
    assert call_session.post_call_processed is False


def test_process_session_rejection_does_not_mark_processed() -> None:
    with _session() as session:
        request, call_session = _seed_completed_call(session)
        adapter = MagicMock()
        adapter.send_email = AsyncMock(return_value={"status_code": 500, "message_id": ""})

        with (
            patch.object(postcall_worker.settings, "TEAM_NOTIFICATION_EMAIL", "ops@example.com"),
            patch.object(postcall_worker, "resolve_email_adapter", return_value=adapter),
            pytest.raises(RuntimeError, match="rejected"),
        ):
            _run(postcall_worker._process_session(session, request, call_session))

        outbox = session.exec(select(OutboxEvent)).all()

    adapter.send_email.assert_awaited_once()
    assert outbox[0].published_at is None
    assert call_session.post_call_processed is False
