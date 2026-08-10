from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain.scheduling.models import SchedulingRequest, SchedulingRequestStatus
from app.domain.signals.models import SignalEvent
from app.domain_models import Campaign, Contact


def _state_token(request_id: uuid.UUID, workspace_id: str, *, expires_at: int | None = None) -> str:
    payload = json.dumps(
        {
            "requestId": str(request_id),
            "workspace": workspace_id,
            "exp": expires_at or int(time.time()) + 300,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(settings.SECRET_KEY.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _payload(request_id: uuid.UUID, workspace_id: str, *, token: str | None = None) -> dict:
    return {
        "event": "invitee.created",
        "payload": {
            "tracking": {
                "utm_content": token or _state_token(request_id, workspace_id),
            },
            "event": {"uri": "event-1", "start_time": "2026-08-10T12:00:00+00:00"},
        },
    }


def _signature(body: bytes, key: str, timestamp: str | None = None) -> str:
    timestamp = timestamp or str(int(time.time()))
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


def test_calendly_webhook_rejects_stale_signed_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "secret"
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", key, raising=False)
    body = json.dumps({"event": "ping"}).encode()

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        content=body,
        headers={"Calendly-Webhook-Signature": _signature(body, key, timestamp="123")},
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


def test_calendly_webhook_rejects_expired_state_token(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "secret"
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", key, raising=False)
    scheduling_request = _seed_request(db)
    body = json.dumps(
        _payload(
            scheduling_request.id,
            "workspace-a",
            token=_state_token(scheduling_request.id, "workspace-a", expires_at=1),
        ),
        separators=(",", ":"),
    ).encode()

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        content=body,
        headers={"Content-Type": "application/json", "Calendly-Webhook-Signature": _signature(body, key)},
    )

    assert response.status_code == 403
    db.refresh(scheduling_request)
    assert scheduling_request.status == SchedulingRequestStatus.pending


def test_calendly_webhook_rejects_legacy_raw_utm_identifiers(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = "secret"
    monkeypatch.setattr(settings, "CALENDLY_WEBHOOK_SIGNING_KEY", key, raising=False)
    scheduling_request = _seed_request(db)
    payload = _payload(scheduling_request.id, "workspace-a")
    payload["payload"]["tracking"] = {
        "utm_content": str(scheduling_request.id),
        "utm_source": "workspace-a",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()

    response = client.post(
        f"{settings.API_V1_STR}/scheduling/webhooks/calendly",
        content=body,
        headers={"Content-Type": "application/json", "Calendly-Webhook-Signature": _signature(body, key)},
    )

    assert response.status_code == 403
