from __future__ import annotations

import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.scheduling.models import SchedulingRequest, SchedulingRequestStatus
from app.domain.signals.models import SignalEvent
from app.domain_models import Campaign, Contact


def _payload(request_id: uuid.UUID, workspace_id: str) -> dict:
    return {
        "event": "invitee.created",
        "payload": {
            "tracking": {
                "utm_content": str(request_id),
                "utm_source": workspace_id,
            },
            "event": {"uri": "event-1", "start_time": "2026-08-10T12:00:00+00:00"},
        },
    }


def _signature(body: bytes, key: str, timestamp: str = "123") -> str:
    digest = hmac.new(key.encode(), timestamp.encode() + b"." + body, hashlib.sha256)
    return f"t={timestamp},v1={digest.hexdigest()}"


def _seed_request(db: Session, workspace_id: str = "workspace-a") -> SchedulingRequest:
    campaign = Campaign(
        name="Calendly campaign", workspace_id=workspace_id, created_by=uuid.uuid4()
    )
    contact = Contact(workspace_id=workspace_id, email="calendar@example.com")
    db.add(campaign)
    db.add(contact)
    db.flush()
    signal = SignalEvent(
        workspace_id=workspace_id,
        shared_contact_id=contact.id,
        campaign_id=campaign.id,
        channel="voice",
        signal_type="scheduling_requested",
    )
    db.add(signal)
    db.flush()
    request = SchedulingRequest(
        workspace_id=workspace_id,
        contact_id=contact.id,
        campaign_id=campaign.id,
        signal_event_id=signal.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def test_calendly_webhook_fails_closed_when_signing_key_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", "", raising=False)

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        json={"event": "ping"},
    )

    assert response.status_code == 503


@pytest.mark.parametrize("signature", ["", "t=123,v1=forged"])
def test_calendly_webhook_rejects_missing_or_forged_signature(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    signature: str,
) -> None:
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", "secret", raising=False)

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        content=json.dumps({"event": "ping"}),
        headers={"Calendly-Webhook-Signature": signature},
    )

    assert response.status_code == 403


def test_calendly_webhook_rejects_cross_workspace_request_attachment(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "secret"
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", key, raising=False)
    scheduling_request = _seed_request(db)
    body = json.dumps(
        _payload(scheduling_request.id, "workspace-b"), separators=(",", ":")
    ).encode()

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Calendly-Webhook-Signature": _signature(body, key),
        },
    )

    assert response.status_code == 404
    db.refresh(scheduling_request)
    assert scheduling_request.status == SchedulingRequestStatus.pending
