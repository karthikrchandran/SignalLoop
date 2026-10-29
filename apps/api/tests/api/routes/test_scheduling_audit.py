import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import scheduling
from app.domain.audit.audit_events import AuditEvent
from app.domain.scheduling.models import SchedulingRequest
from app.domain_models import Campaign, Contact


def _context(db: Session) -> tuple[str, uuid.UUID, uuid.UUID]:
    workspace = f"schedule-{uuid.uuid4().hex[:12]}"
    campaign = Campaign(workspace_id=workspace, name="Audit regression", created_by=uuid.uuid4())
    contact = Contact(workspace_id=workspace, email=f"{uuid.uuid4().hex}@example.com")
    db.add_all([campaign, contact])
    db.commit()
    return workspace, campaign.id, contact.id


def test_scheduling_create_update_emit_owned_audits(
    db: Session, client: TestClient, superuser_token_headers: dict[str, str],
) -> None:
    workspace, campaign_id, contact_id = _context(db)
    headers = {**superuser_token_headers, "X-Workspace-Id": workspace}
    response = client.post("/api/v1/scheduling/requests", headers=headers, json={
        "campaign_id": str(campaign_id), "contact_id": str(contact_id),
    })
    assert response.status_code == 201
    request_id = response.json()["id"]
    response = client.patch(
        f"/api/v1/scheduling/requests/{request_id}", headers=headers,
        json={"notes": "Audit regression update"},
    )
    assert response.status_code == 200
    assert response.json()["notes"] == "Audit regression update"
    response = client.get("/api/v1/scheduling/requests", headers=headers)
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == [request_id]
    events = db.exec(select(AuditEvent).where(
        AuditEvent.workspace_id == workspace,
        AuditEvent.resource_id == request_id,
    )).all()
    assert {event.event_name for event in events} == {
        "scheduling_request.created", "scheduling_request.updated",
    }
    assert all(event.resource_type == "SchedulingRequest" for event in events)
    assert all(event.actor_id is not None for event in events)
    assert next(event.payload for event in events if event.event_name.endswith(".updated")) == {
        "notes": "Audit regression update",
    }


def test_failed_scheduling_audit_rolls_back_creation(
    db: Session, client: TestClient, superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, campaign_id, contact_id = _context(db)

    def reject_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit write unavailable")

    monkeypatch.setattr(scheduling, "append_audit_event_to_session", reject_audit)
    with pytest.raises(RuntimeError, match="audit write unavailable"):
        client.post("/api/v1/scheduling/requests", headers={
            **superuser_token_headers, "X-Workspace-Id": workspace,
        }, json={"campaign_id": str(campaign_id), "contact_id": str(contact_id)})
    db.expire_all()
    assert db.exec(select(SchedulingRequest).where(
        SchedulingRequest.workspace_id == workspace,
    )).all() == []


def test_failed_scheduling_audit_rolls_back_update(
    db: Session, client: TestClient, superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, campaign_id, contact_id = _context(db)
    request = SchedulingRequest(
        workspace_id=workspace, campaign_id=campaign_id, contact_id=contact_id,
        notes="Original notes",
    )
    db.add(request)
    db.commit()
    request_id = request.id

    def reject_audit(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("audit write unavailable")

    monkeypatch.setattr(scheduling, "append_audit_event_to_session", reject_audit)
    with pytest.raises(RuntimeError, match="audit write unavailable"):
        client.patch(
            f"/api/v1/scheduling/requests/{request_id}",
            headers={**superuser_token_headers, "X-Workspace-Id": workspace},
            json={"notes": "Must roll back"},
        )
    db.refresh(request)
    assert request.notes == "Original notes"
