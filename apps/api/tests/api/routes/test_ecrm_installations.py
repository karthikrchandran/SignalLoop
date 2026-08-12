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


def test_binding_route_uses_header_workspace_and_never_returns_secret(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    workspace_id = f"install-{uuid4().hex[:8]}"
    cell_id = f"cell-{workspace_id}"
    cell_key = f"key-{workspace_id}"
    _workspace_admin(db, workspace_id)
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_ENDPOINTS",
        {
            "endpoint-primary": {
                "ecrm_cell_id": cell_id,
                "ecrm_cell_key": cell_key,
                "base_url": "https://cell.invalid",
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_SECRET_REFERENCES",
        {
            "secret-primary": {
                "ecrm_cell_id": cell_id,
                "environment_name": "ECRM_CELL_SECRET",
            }
        },
    )
    response = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json={
            "endpoint_id": "endpoint-primary",
            "secret_reference_id": "secret-primary",
            "capabilities": ["WORKFLOW_EVENT"],
            "status": "ACTIVE",
            "source_version": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["workspace_id"] == workspace_id
    assert "credential_secret_ref" not in response.json()
    assert db.get(EcrmInstallationBinding, workspace_id) is not None


def test_binding_route_rejects_exfiltration_url_and_environment_reference(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"install-exfil-{uuid4().hex[:8]}"
    _workspace_admin(db, workspace_id)

    response = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json={
            "endpoint_id": "endpoint-primary",
            "secret_reference_id": "secret-primary",
            "base_url": "https://attacker.invalid/collect",
            "credential_secret_ref": "env://DATABASE_URL",
            "capabilities": ["WORKFLOW_EVENT"],
            "status": "ACTIVE",
            "source_version": 1,
        },
    )

    assert response.status_code == 422
    assert db.get(EcrmInstallationBinding, workspace_id) is None


def test_binding_route_rejects_unprovisioned_destination_identifiers(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"install-unprovisioned-{uuid4().hex[:8]}"
    _workspace_admin(db, workspace_id)

    response = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json={
            "endpoint_id": "attacker-endpoint",
            "secret_reference_id": "attacker-secret",
            "capabilities": ["WORKFLOW_EVENT"],
            "status": "ACTIVE",
            "source_version": 1,
        },
    )

    assert response.status_code == 422
    assert db.get(EcrmInstallationBinding, workspace_id) is None


def test_binding_route_cannot_retarget_an_existing_installation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    workspace_id = f"install-immutable-{uuid4().hex[:8]}"
    cell_id = f"cell-{workspace_id}"
    _workspace_admin(db, workspace_id)
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_ENDPOINTS",
        {
            "endpoint-primary": {
                "ecrm_cell_id": cell_id,
                "ecrm_cell_key": f"key-{workspace_id}",
                "base_url": "https://cell.invalid",
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_SECRET_REFERENCES",
        {
            "secret-primary": {
                "ecrm_cell_id": cell_id,
                "environment_name": "ECRM_CELL_SECRET",
            }
        },
    )
    body = {
        "endpoint_id": "endpoint-primary",
        "secret_reference_id": "secret-primary",
        "capabilities": ["WORKFLOW_EVENT"],
        "status": "ACTIVE",
        "source_version": 1,
    }
    first = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json=body,
    )
    assert first.status_code == 200

    settings.ECRM_INSTALLATION_ENDPOINTS["endpoint-primary"]["base_url"] = (
        "https://attacker.invalid"
    )
    retarget = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
        json=body,
    )

    assert retarget.status_code == 422
    db.expire_all()
    assert db.get(EcrmInstallationBinding, workspace_id).base_url == "https://cell.invalid"


def test_delivery_route_requires_cell_credential_and_rejects_workspace_override(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    suffix = uuid4().hex[:8]
    cell_id = f"route-cell-{suffix}"
    binding = EcrmInstallationBinding(
        workspace_id=f"route-ws-{suffix}",
        ecrm_cell_id=cell_id,
        ecrm_cell_key=f"route-key-{suffix}",
        base_url="https://cell.invalid",
        credential_secret_ref="route-secret",
        capabilities=["WORKFLOW_EVENT"],
    )
    db.add(binding)
    db.commit()
    monkeypatch.setenv("ROUTE_ECRM_SECRET", "route-token")
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_ENDPOINTS",
        {
            "route-endpoint": {
                "ecrm_cell_id": cell_id,
                "ecrm_cell_key": binding.ecrm_cell_key,
                "base_url": binding.base_url,
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_SECRET_REFERENCES",
        {
            "route-secret": {
                "ecrm_cell_id": cell_id,
                "environment_name": "ROUTE_ECRM_SECRET",
            }
        },
    )
    response = client.post(
        f"{settings.API_V1_STR}/ecrm-installations/deliveries?workspace_id=attacker",
        headers={
            "X-ECRM-Cell-Id": cell_id,
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
