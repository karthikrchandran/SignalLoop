"""Unit tests for Twilio webhook replay helpers."""
from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.voice import (
    _record_twilio_provider_event,
    _twilio_provider_event_id,
)
from app.domain_models import NotificationProvider, ProviderEventLog


def test_twilio_provider_event_id_is_stable_and_scoped_by_event_kind() -> None:
    params = {
        "CallSid": "CA123",
        "AccountSid": "AC123",
        "CallStatus": "ringing",
    }

    first = _twilio_provider_event_id("status", params)
    second = _twilio_provider_event_id("status", dict(params))
    recording = _twilio_provider_event_id(
        "recording",
        {
            "CallSid": "CA123",
            "AccountSid": "AC123",
            "RecordingSid": "RE123",
        },
    )

    assert first == second
    assert first.startswith("twilio:status:")
    assert recording.startswith("twilio:recording:")
    assert first != recording


def test_record_twilio_provider_event_returns_false_for_replay() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[ProviderEventLog.__table__])

    with Session(engine) as session:
        first = _record_twilio_provider_event(
            session,
            workspace_id="ws",
            provider_event_id="twilio:status:abc",
            event_type="twilio_call_status",
            raw_payload={"CallSid": "CA123", "CallStatus": "ringing"},
            normalized_event={"call_sid": "CA123", "call_status": "ringing"},
        )
        session.commit()

        replay = _record_twilio_provider_event(
            session,
            workspace_id="ws",
            provider_event_id="twilio:status:abc",
            event_type="twilio_call_status",
            raw_payload={"CallSid": "CA123", "CallStatus": "ringing"},
            normalized_event={"call_sid": "CA123", "call_status": "ringing"},
        )
        rows = session.exec(
            select(ProviderEventLog).where(
                ProviderEventLog.provider == NotificationProvider.twilio,
            )
        ).all()

    assert first is True
    assert replay is False
    assert len(rows) == 1


def test_record_twilio_provider_event_treats_unique_conflict_as_replay(
    monkeypatch,
) -> None:
    """A callback race must not escape as a database integrity failure."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine, tables=[ProviderEventLog.__table__])

    with Session(engine) as session:
        session.add(
            ProviderEventLog(
                workspace_id="ws",
                provider=NotificationProvider.twilio,
                provider_event_id="twilio:status:raced",
                event_type="twilio_call_status",
            )
        )
        session.commit()

        # Model the narrow window where another callback commits after our
        # duplicate pre-check but before our insert is flushed.
        original_exec = session.exec
        monkeypatch.setattr(
            session,
            "exec",
            lambda statement: type("NoExistingEvent", (), {"first": lambda self: None})(),
        )
        replay = _record_twilio_provider_event(
            session,
            workspace_id="ws",
            provider_event_id="twilio:status:raced",
            event_type="twilio_call_status",
            raw_payload={"CallSid": "CA123", "CallStatus": "ringing"},
            normalized_event={"call_sid": "CA123", "call_status": "ringing"},
        )
        monkeypatch.setattr(session, "exec", original_exec)

        assert replay is False
        session.commit()
