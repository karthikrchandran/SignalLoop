"""Tests for audit log query and export API (Story 5.2)."""
from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.middleware import request_id_var
from app.domain.audit.audit_events import AuditEvent, build_audit_event

WORKSPACE_ID = "ws-audit-log-test"
OTHER_WORKSPACE_ID = "ws-audit-log-other"


def _headers(token_headers: dict[str, str], *, workspace_id: str = WORKSPACE_ID) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def _seed_event(
    db: Session,
    workspace_id: str = WORKSPACE_ID,
    event_name: str = "campaign.created",
    actor_id: uuid.UUID | None = None,
    correlation_id: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_name=event_name,
        workspace_id=workspace_id,
        actor_id=actor_id or uuid.uuid4(),
        actor_role="admin",
        resource_type="campaign",
        resource_id=str(uuid.uuid4()),
        correlation_id=correlation_id,
        payload={"test": True},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def test_admin_can_query_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_event(db)
    response = client.get(
        f"{settings.API_V1_STR}/audit-log",
        headers=_headers(superuser_token_headers),
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_audit_log_cross_workspace_isolation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_event(db, workspace_id=OTHER_WORKSPACE_ID, event_name="campaign.created.isolation")
    response = client.get(
        f"{settings.API_V1_STR}/audit-log",
        headers=_headers(superuser_token_headers, workspace_id=WORKSPACE_ID),
        params={"action_type": "campaign.created.isolation"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_audit_log_filter_by_action_type(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_event(db, event_name="policy.created")
    response = client.get(
        f"{settings.API_V1_STR}/audit-log",
        headers=_headers(superuser_token_headers),
        params={"action_type": "policy.created"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(item["event_name"] == "policy.created" for item in data["items"])


def test_audit_log_filter_by_actor_and_correlation_id(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    actor_id = uuid.uuid4()
    correlation_id = f"corr-{uuid.uuid4()}"
    _seed_event(
        db,
        event_name="policy.filtered",
        actor_id=actor_id,
        correlation_id=correlation_id,
    )
    _seed_event(db, event_name="policy.filtered", actor_id=uuid.uuid4(), correlation_id="other")

    response = client.get(
        f"{settings.API_V1_STR}/audit-log",
        headers=_headers(superuser_token_headers),
        params={
            "action_type": "policy.filtered",
            "actor_id": str(actor_id),
            "correlation_id": correlation_id,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["actor_id"] == str(actor_id)
    assert data["items"][0]["correlation_id"] == correlation_id


def test_build_audit_event_defaults_correlation_from_request_context() -> None:
    token = request_id_var.set("req-audit-123")
    try:
        event = build_audit_event(event_name="campaign.created", workspace_id=WORKSPACE_ID)
    finally:
        request_id_var.reset(token)

    assert event.correlation_id == "req-audit-123"


def test_audit_log_export_json(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_event(db, event_name="sequence.created", correlation_id="corr-export-json")
    # Request export job
    export_response = client.post(
        f"{settings.API_V1_STR}/audit-log/export",
        headers=_headers(superuser_token_headers),
        json={"format": "json", "action_type": "sequence.created"},
    )
    assert export_response.status_code == 200
    export_data = export_response.json()
    assert export_data["status"] == "complete"
    job_id = export_data["job_id"]

    # Download exported file
    download_response = client.get(
        f"{settings.API_V1_STR}/audit-log/export/{job_id}",
        headers=_headers(superuser_token_headers),
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("application/json")
    rows = json.loads(download_response.text)
    assert rows
    assert all(row["workspace_id"] == WORKSPACE_ID for row in rows)
    assert any(row["correlation_id"] == "corr-export-json" for row in rows)


def test_audit_log_export_csv(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    _seed_event(db, event_name="template_published", correlation_id="corr-export-csv")
    export_response = client.post(
        f"{settings.API_V1_STR}/audit-log/export",
        headers=_headers(superuser_token_headers),
        json={"format": "csv", "action_type": "template_published"},
    )
    assert export_response.status_code == 200
    job_id = export_response.json()["job_id"]

    download_response = client.get(
        f"{settings.API_V1_STR}/audit-log/export/{job_id}",
        headers=_headers(superuser_token_headers),
    )
    assert download_response.status_code == 200
    assert "text/csv" in download_response.headers["content-type"]
    rows = list(csv.DictReader(io.StringIO(download_response.text)))
    assert rows
    assert all(row["workspace_id"] == WORKSPACE_ID for row in rows)
    assert any(row["correlation_id"] == "corr-export-csv" for row in rows)


def test_audit_log_pagination(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    ws = "ws-audit-pagination-test"
    for _ in range(5):
        _seed_event(db, workspace_id=ws, event_name="campaign.created")

    response = client.get(
        f"{settings.API_V1_STR}/audit-log",
        headers=_headers(superuser_token_headers, workspace_id=ws),
        params={"limit": 2, "page": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 2
    assert data["total"] >= 5
