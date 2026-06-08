"""Unit tests for call manual action hardening."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes import calls
from app.domain.audit.audit_events import AuditEvent
from app.domain.voice.models import CallOutcome, CallRequest, CallSession, VoiceScript
from app.domain_models import Campaign, Contact, OutboxEvent


def _run(coro):
    return asyncio.run(coro)


class _FakeEmailAdapter:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_email(self, **kwargs):
        self.sent.append(kwargs)
        return {"status_code": 202, "message_id": "msg-1"}


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _seed_call(
    session: Session, *, workspace_id: str = "ws"
) -> tuple[Contact, CallRequest]:
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

    script = VoiceScript(
        campaign_id=campaign.id,
        name="Script",
        content="Say hello.",
        created_by=owner_id,
    )
    session.add(script)
    session.flush()

    call_request = CallRequest(
        contact_id=contact.id,
        campaign_id=campaign.id,
        voice_script_id=script.id,
        trigger_reason="manual",
        scheduled_at=datetime.now(timezone.utc),
    )
    session.add(call_request)
    session.commit()
    session.refresh(contact)
    session.refresh(call_request)
    return contact, call_request


def _user():
    return SimpleNamespace(id=uuid.uuid4(), is_superuser=True)


def test_send_demo_email_once_uses_provider_resolver_and_outbox(monkeypatch) -> None:
    adapter = _FakeEmailAdapter()
    monkeypatch.setattr(
        calls, "_email_adapter", lambda _session, _workspace_id: adapter
    )

    with _session() as session:
        _, call_request = _seed_call(session)

        result = _run(
            calls._send_demo_email_once(
                session=session,
                current_user=_user(),
                workspace_id="ws",
                call_request_id=call_request.id,
            )
        )
        second = _run(
            calls._send_demo_email_once(
                session=session,
                current_user=_user(),
                workspace_id="ws",
                call_request_id=call_request.id,
            )
        )
        outbox = session.exec(select(OutboxEvent)).all()

    assert result == {"message": "Demo email sent"}
    assert second == {"message": "Demo email already sent"}
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["idempotency_key"] == (
        f"call_request:{call_request.id}:send_demo_email"
    )
    assert len(outbox) == 1
    assert outbox[0].published_at is not None


def test_flag_for_sales_once_uses_provider_resolver_and_outbox(monkeypatch) -> None:
    adapter = _FakeEmailAdapter()
    monkeypatch.setattr(
        calls, "_email_adapter", lambda _session, _workspace_id: adapter
    )
    monkeypatch.setattr(
        calls,
        "resolve_team_notification_email",
        lambda _session, _workspace_id: "team@example.com",
    )

    with _session() as session:
        _, call_request = _seed_call(session)

        result = _run(
            calls._flag_for_sales_once(
                session=session,
                current_user=_user(),
                workspace_id="ws",
                call_request_id=call_request.id,
            )
        )
        second = _run(
            calls._flag_for_sales_once(
                session=session,
                current_user=_user(),
                workspace_id="ws",
                call_request_id=call_request.id,
            )
        )
        outbox = session.exec(select(OutboxEvent)).all()

    assert result == {"message": "Contact flagged for sales team"}
    assert second == {"message": "Contact already flagged for sales team"}
    assert len(adapter.sent) == 1
    assert adapter.sent[0]["to"] == "team@example.com"
    assert adapter.sent[0]["idempotency_key"] == (
        f"call_request:{call_request.id}:flag_for_sales"
    )
    assert len(outbox) == 1
    assert outbox[0].published_at is not None


def test_queue_test_call_creates_queued_request_and_audit_event() -> None:
    with _session() as session:
        contact, source_call = _seed_call(session)
        expected_campaign_id = source_call.campaign_id
        expected_script_id = source_call.voice_script_id

        payload = calls.TestCallCreate(
            contact_id=contact.id,
            campaign_id=expected_campaign_id,
            voice_script_id=expected_script_id,
        )
        result = calls._queue_test_call_once(
            session=session,
            current_user=_user(),
            workspace_id="ws",
            payload=payload,
        )
        queued_call = session.get(CallRequest, result.call_request_id)
        audit_events = session.exec(select(AuditEvent)).all()

    assert result.status == "queued"
    assert result.message == "Test call queued"
    assert queued_call is not None
    assert queued_call.contact_id == contact.id
    assert queued_call.campaign_id == expected_campaign_id
    assert queued_call.voice_script_id == expected_script_id
    assert queued_call.trigger_reason == "manual_test_call"
    assert audit_events[-1].event_name == "call.test_call_queued"


def test_call_detail_returns_outcome_intelligence() -> None:
    with _session() as session:
        _, call_request = _seed_call(session)
        session.add(
            CallSession(
                call_request_id=call_request.id,
                twilio_call_sid="CA123",
                outcome=CallOutcome.answered,
                duration_seconds=96,
                transcript=(
                    "Ada said they are interested but need pricing clarity "
                    "before booking the demo next Tuesday."
                ),
                unanswered_questions={
                    "questions": ["pricing clarity before booking a demo"],
                },
                scheduling_interest=True,
            )
        )
        session.commit()

        result = calls.get_call_detail(
            session=session,
            workspace_id="ws",
            call_request_id=call_request.id,
        )

    assert result.intelligence is not None
    assert "pricing clarity" in result.intelligence.summary
    assert result.intelligence.sentiment == "positive"
    assert result.intelligence.objection == "pricing clarity before booking a demo"
    assert result.intelligence.next_action == "Book the requested meeting time."
    assert "pricing clarity" in result.intelligence.recommended_follow_up
