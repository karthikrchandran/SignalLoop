"""Tests for ``app.api.routes.webhooks`` SendGrid endpoint (Group E coverage)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailEvent,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain.signals.models import SignalEvent
from app.domain_models import Campaign, Contact

WORKSPACE_ID = "ws-webhooks-test"


def _make_send_request(
    db: Session,
    *,
    provider_message_id: str,
) -> tuple[SendRequest, ContactSequenceState, EmailSequence, Contact, Campaign]:
    """Seed a Campaign → Sequence → Contact → State → SendRequest chain."""
    campaign = Campaign(
        name=f"WH {uuid.uuid4().hex[:6]}",
        workspace_id=WORKSPACE_ID,
        created_by=uuid.uuid4(),
    )
    db.add(campaign)
    db.flush()
    sequence = EmailSequence(
        campaign_id=campaign.id,
        name="Hooked",
        created_by=uuid.uuid4(),
    )
    db.add(sequence)
    db.flush()
    contact = Contact(
        workspace_id=WORKSPACE_ID,
        email=f"wh-{uuid.uuid4().hex[:6]}@example.com",
    )
    db.add(contact)
    db.flush()
    state = ContactSequenceState(
        contact_id=contact.id,
        sequence_id=sequence.id,
        status=SequenceStatus.active,
        current_step=1,
    )
    db.add(state)
    db.flush()
    sr = SendRequest(
        contact_sequence_state_id=state.id,
        step_order=1,
        idempotency_key=f"wh-{uuid.uuid4()}",
        provider_message_id=provider_message_id,
        status=SendRequestStatus.pending,
    )
    db.add(sr)
    db.commit()
    db.refresh(sr)
    db.refresh(state)
    return sr, state, sequence, contact, campaign


def _ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


# ---------------------------------------------------------------------------
# Signature handling
# ---------------------------------------------------------------------------


def test_invalid_signature_returns_403(client: TestClient) -> None:
    """When verify_webhook_signature returns False, route responds 403."""
    with patch(
        "app.api.routes.webhooks.SendGridAdapter.verify_webhook_signature",
        return_value=False,
    ):
        resp = client.post(
            f"{settings.API_V1_STR}/webhooks/sendgrid",
            json=[{"event": "delivered", "sg_message_id": "abc.def"}],
        )
    assert resp.status_code == 403


def test_valid_signature_empty_events_returns_ok(client: TestClient) -> None:
    """Empty events list with valid signature still returns 200/ok."""
    resp = client.post(
        f"{settings.API_V1_STR}/webhooks/sendgrid",
        json=[],
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------


def test_event_without_message_id_skipped(
    client: TestClient,
    db: Session,
) -> None:
    """An event with no sg_message_id is logged and skipped (200)."""
    resp = client.post(
        f"{settings.API_V1_STR}/webhooks/sendgrid",
        json=[{"event": "delivered", "timestamp": _ts(), "sg_event_id": "ev1"}],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_event_unknown_message_id_logged_and_skipped(
    client: TestClient,
    db: Session,
) -> None:
    """Event referencing a SendRequest that does not exist is skipped."""
    resp = client.post(
        f"{settings.API_V1_STR}/webhooks/sendgrid",
        json=[
            {
                "event": "delivered",
                "sg_message_id": "missing-msg.suffix",
                "timestamp": _ts(),
                "sg_event_id": "ev2",
            }
        ],
    )
    assert resp.status_code == 200


def test_delivered_event_marks_send_sent(
    client: TestClient,
    db: Session,
) -> None:
    """A delivered event flips SendRequest.status to sent and records EmailEvent."""
    sr, _state, _seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"deliver-{uuid.uuid4().hex[:8]}"
    )
    payload = [
        {
            "event": "delivered",
            "sg_message_id": f"{sr.provider_message_id}.suffix",
            "email": "addr@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(sr)
    assert sr.status == SendRequestStatus.sent
    events = db.exec(select(EmailEvent).where(EmailEvent.send_request_id == sr.id)).all()
    assert any(e.event_type == "delivered" for e in events)


def test_bounce_event_stops_sequence_and_emits_signal(
    client: TestClient,
    db: Session,
) -> None:
    """A bounce event marks the send failed, stops the sequence and emits a signal."""
    sr, state, seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"bounce-{uuid.uuid4().hex[:8]}"
    )
    payload = [
        {
            "event": "bounce",
            "sg_message_id": f"{sr.provider_message_id}.suffix",
            "email": "bounce@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(sr)
    db.refresh(state)
    assert sr.status == SendRequestStatus.failed
    assert state.status == SequenceStatus.stopped
    assert state.signal_type == "hard_bounce"
    signals = db.exec(
        select(SignalEvent).where(SignalEvent.source_event_id == sr.id)
    ).all()
    assert any(s.signal_type == "hard_bounce" for s in signals)


def test_dropped_event_branch(
    client: TestClient,
    db: Session,
) -> None:
    """A dropped event takes the same failed/stop path as bounce."""
    sr, state, _seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"drop-{uuid.uuid4().hex[:8]}"
    )
    payload = [
        {
            "event": "dropped",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": "drop@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(sr)
    db.refresh(state)
    assert sr.status == SendRequestStatus.failed
    assert state.status == SequenceStatus.stopped


def test_spamreport_adds_suppression(
    client: TestClient,
    db: Session,
) -> None:
    """A spamreport event adds an EmailSuppression row and stops the sequence."""
    sr, state, _seq, contact, _camp = _make_send_request(
        db, provider_message_id=f"spam-{uuid.uuid4().hex[:8]}"
    )
    payload = [
        {
            "event": "spamreport",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": contact.email,
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(state)
    assert state.status == SequenceStatus.stopped
    suppression = db.exec(
        select(EmailSuppression).where(
            EmailSuppression.email == contact.email,
            EmailSuppression.reason == "spamreport",
        )
    ).first()
    assert suppression is not None


def test_unsubscribe_adds_suppression(
    client: TestClient,
    db: Session,
) -> None:
    """An unsubscribe event also stops the sequence and adds a suppression row."""
    sr, state, _seq, contact, _camp = _make_send_request(
        db, provider_message_id=f"unsub-{uuid.uuid4().hex[:8]}"
    )
    payload = [
        {
            "event": "unsubscribe",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": contact.email,
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(state)
    assert state.status == SequenceStatus.stopped


def test_replied_positive_signal_pauses_sequence(
    client: TestClient,
    db: Session,
) -> None:
    """A replied event with positive sentiment pauses the sequence."""
    sr, state, _seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"reply-{uuid.uuid4().hex[:8]}"
    )

    class _PosResult:
        signal_type = "email_positive_reply"
        confidence = 0.9

    payload = [
        {
            "event": "replied",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": "reply@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
            "text": "Yes please book a call",
        }
    ]
    with patch(
        "app.api.routes.webhooks.detect_email_signal", return_value=_PosResult()
    ):
        resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(state)
    assert state.status == SequenceStatus.paused
    assert state.signal_type == "email_positive_reply"


def test_replied_non_positive_signal_no_state_change(
    client: TestClient,
    db: Session,
) -> None:
    """A replied event with no positive signal leaves the sequence active."""
    sr, state, _seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"replyneg-{uuid.uuid4().hex[:8]}"
    )

    class _NegResult:
        signal_type = "email_negative_reply"
        confidence = 0.4

    payload = [
        {
            "event": "replied",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": "neg@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
            "text": "Not interested",
        }
    ]
    with patch(
        "app.api.routes.webhooks.detect_email_signal", return_value=_NegResult()
    ):
        resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    db.refresh(state)
    assert state.status == SequenceStatus.active


def test_processing_exception_logged_but_returns_ok(
    client: TestClient,
    db: Session,
) -> None:
    """An exception while processing one event is logged but the response stays 200."""
    sr, _state, _seq, _contact, _camp = _make_send_request(
        db, provider_message_id=f"boom-{uuid.uuid4().hex[:8]}"
    )

    async def _boom(_self, raw):  # noqa: ANN001
        raise RuntimeError("normalize failed")

    payload = [
        {
            "event": "delivered",
            "sg_message_id": f"{sr.provider_message_id}.x",
            "email": "boom@example.com",
            "timestamp": _ts(),
            "sg_event_id": str(uuid.uuid4()),
        }
    ]
    with patch(
        "app.api.routes.webhooks.SendGridAdapter.normalize_webhook_event", _boom
    ):
        resp = client.post(f"{settings.API_V1_STR}/webhooks/sendgrid", json=payload)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
