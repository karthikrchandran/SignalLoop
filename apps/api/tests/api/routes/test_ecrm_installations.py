from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.workspaces.service import ensure_workspace, ensure_workspace_membership
from app.models import User


def _workspace_admin(db: Session, workspace_id: str) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    ensure_workspace(db, workspace_id=workspace_id, display_name=workspace_id)
    ensure_workspace_membership(db, workspace_id=workspace_id, user_id=user.id, role="admin")
    db.commit()
    return user


def test_binding_route_ignores_body_workspace_and_never_returns_secret(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"install-{uuid4().hex[:8]}"
    _workspace_admin(db, workspace_id)
    response = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json={
            "workspace_id": "attacker-workspace",
            "ecrm_cell_id": f"cell-{workspace_id}",
            "ecrm_cell_key": f"key-{workspace_id}",
            "base_url": "https://cell.invalid",
            "credential_secret_ref": "env://ECRM_CELL_SECRET",
            "capabilities": ["WORKFLOW_EVENT"],
            "status": "ACTIVE",
            "source_version": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["workspace_id"] == workspace_id
    assert "credential_secret_ref" not in response.json()
    assert db.get(EcrmInstallationBinding, workspace_id) is not None
    assert db.get(EcrmInstallationBinding, "attacker-workspace") is None


def test_delivery_route_requires_cell_credential_and_rejects_workspace_override(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    suffix = uuid4().hex[:8]
    binding = EcrmInstallationBinding(
        workspace_id=f"route-ws-{suffix}",
        ecrm_cell_id=f"route-cell-{suffix}",
        ecrm_cell_key=f"route-key-{suffix}",
        base_url="https://cell.invalid",
        credential_secret_ref="env://ROUTE_ECRM_SECRET",
        capabilities=["WORKFLOW_EVENT"],
    )
    db.add(binding)
    db.commit()
    monkeypatch.setenv("ROUTE_ECRM_SECRET", "route-token")
    response = client.post(
        f"{settings.API_V1_STR}/ecrm-installations/deliveries?workspace_id=attacker",
        headers={
            "X-ECRM-Cell-Id": f"route-cell-{suffix}",
            "Authorization": "Bearer route-token",
            "Idempotency-Key": "route-event",
        },
        json={
            "source_event_id": "route-event",
            "source_version": 1,
            "stream_key": "installation:route",
            "event_kind": "WORKFLOW_EVENT",
            "payload": {"workspace_id": "attacker"},
        },
    )

    assert response.status_code == 202
    assert response.json()["workspace_id"] == f"route-ws-{suffix}"
    assert response.json()["source_event_id"] == "route-event"
