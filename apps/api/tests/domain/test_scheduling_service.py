"""Unit tests for ``app.domain.scheduling.service``."""

from __future__ import annotations

import time
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.domain.scheduling import service as scheduling_service
from app.domain.scheduling.models import (
    SchedulingRequest,
    SchedulingRequestSource,
    SchedulingRequestStatus,
)
from app.domain.scheduling.schemas import (
    SchedulingRequestCreate,
    SchedulingRequestUpdate,
)
from app.domain.scheduling.service import (
    create_from_call_session,
    create_scheduling_request,
    get_scheduling_request_or_404,
    handle_calendly_booking,
    update_scheduling_request,
    verify_calendly_signature,
)
from app.domain_models import (
    Campaign,
    Contact,
    ContactProgression,
    ContactProgressionState,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _seed_contact(session: Session) -> uuid.UUID:
    contact = Contact(workspace_id="ws_test", email="contact@example.com")
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact.id


def _seed_campaign(session: Session) -> uuid.UUID:
    campaign = Campaign(workspace_id="ws_test", name="Test Campaign", created_by=uuid.uuid4())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign.id


def _seed_progression(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    state: ContactProgressionState = ContactProgressionState.engaged,
) -> None:
    session.add(
        ContactProgression(
            contact_id=contact_id,
            campaign_id=campaign_id,
            current_state=state,
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# create_scheduling_request
# ---------------------------------------------------------------------------


def test_create_scheduling_request_defaults(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)

    req = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )

    assert req.id is not None
    assert req.status == SchedulingRequestStatus.pending
    assert req.source == "manual"
    assert req.meeting_link is None
    assert req.calendly_event_id is None


def test_create_from_call_session_sets_voice_source(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)

    req = create_from_call_session(
        session, contact_id=contact_id, campaign_id=campaign_id
    )

    assert req.source == SchedulingRequestSource.voice_call
    assert req.status == SchedulingRequestStatus.pending


# ---------------------------------------------------------------------------
# get_scheduling_request_or_404
# ---------------------------------------------------------------------------


def test_get_or_404_raises_for_missing(session: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        get_scheduling_request_or_404(session, uuid.uuid4())
    assert exc.value.status_code == 404


def test_get_or_404_returns_existing(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)
    req = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )

    fetched = get_scheduling_request_or_404(session, req.id)
    assert fetched.id == req.id


# ---------------------------------------------------------------------------
# update_scheduling_request
# ---------------------------------------------------------------------------


def test_update_sets_meeting_link_and_advances_to_link_sent(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)
    req = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )

    updated = update_scheduling_request(
        session,
        request_id=req.id,
        data=SchedulingRequestUpdate(meeting_link="https://calendly.com/rep/30min"),
    )

    assert updated.meeting_link == "https://calendly.com/rep/30min"
    assert updated.status == SchedulingRequestStatus.link_sent


def test_update_manual_status_override(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)
    req = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )

    updated = update_scheduling_request(
        session,
        request_id=req.id,
        data=SchedulingRequestUpdate(status=SchedulingRequestStatus.cancelled),
    )

    assert updated.status == SchedulingRequestStatus.cancelled


# ---------------------------------------------------------------------------
# handle_calendly_booking
# ---------------------------------------------------------------------------


def test_handle_calendly_booking_marks_booked(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)
    _seed_progression(session, contact_id, campaign_id)

    req = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )

    meeting_dt = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)
    booked = handle_calendly_booking(
        session,
        workspace_id="ws_test",
        request_id=req.id,
        calendly_event_id="https://api.calendly.com/scheduled_events/abc123",
        meeting_datetime=meeting_dt,
    )

    assert booked.status == SchedulingRequestStatus.booked
    assert booked.calendly_event_id == "https://api.calendly.com/scheduled_events/abc123"
    assert booked.meeting_datetime is not None
    stored = (
        booked.meeting_datetime.replace(tzinfo=None)
        if booked.meeting_datetime.tzinfo
        else booked.meeting_datetime
    )
    assert stored == meeting_dt.replace(tzinfo=None)


def test_calendly_event_id_is_unique_per_workspace() -> None:
    constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in SchedulingRequest.__table__.constraints
        if hasattr(constraint, "columns")
    }
    assert constraints["uq_scheduling_workspace_calendly_event"] == (
        "workspace_id",
        "calendly_event_id",
    )
    # SQLite strips tz info — compare naive datetime components


def test_handle_calendly_booking_emits_a_stable_source_event_id(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    contact_id = _seed_contact(session)
    campaign_id = _seed_campaign(session)
    _seed_progression(session, contact_id, campaign_id)
    request = create_scheduling_request(
        session,
        data=SchedulingRequestCreate(contact_id=contact_id, campaign_id=campaign_id),
    )
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(scheduling_service, "emit_event", emitted.append)

    handle_calendly_booking(
        session,
        workspace_id="ws_test",
        request_id=request.id,
        calendly_event_id="event_123",
        meeting_datetime=datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc),
    )

    assert emitted[0]["sourceEventId"] == f"scheduling-booked:{request.id}"


def test_handle_calendly_booking_raises_for_missing_request(session: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        handle_calendly_booking(
            session,
            workspace_id="ws_test",
            request_id=uuid.uuid4(),
            calendly_event_id="evt_123",
            meeting_datetime=datetime.now(timezone.utc),
        )
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# verify_calendly_signature
# ---------------------------------------------------------------------------


def test_verify_calendly_signature_valid() -> None:
    import hashlib
    import hmac as _hmac

    signing_key = "test_signing_key"
    body = b'{"event": "invitee.created"}'
    timestamp = str(int(time.time()))
    signed_message = f"{timestamp}.{body.decode()}"
    v1 = _hmac.new(
        signing_key.encode(), signed_message.encode(), hashlib.sha256
    ).hexdigest()
    header = f"t={timestamp},v1={v1}"

    assert verify_calendly_signature(body, header, signing_key) is True


def test_verify_calendly_signature_invalid() -> None:
    assert (
        verify_calendly_signature(b"body", "t=123,v1=badhash", "key") is False
    )


def test_verify_calendly_signature_malformed_header() -> None:
    assert verify_calendly_signature(b"body", "not-a-valid-header", "key") is False
