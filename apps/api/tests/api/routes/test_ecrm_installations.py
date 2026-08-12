from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.workspaces.service import ensure_workspace, ensure_workspace_membership
from app.models import User


def _workspace_admin(db: Session, workspace_id: str) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    ensure_workspace(db, workspace_id=workspace_id, display_name=workspace_id)
    ensure_workspace_membership(
        db, workspace_id=workspace_id, user_id=user.id, role="admin"
    )
    db.commit()
    return user


def _contract() -> dict:
    path = (
        Path(__file__).resolve().parents[5]
        / "docs"
        / "contracts"
        / "signalloop-ecrm-installation-delivery-v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _configure_contract_binding(db: Session, monkeypatch) -> EcrmInstallationBinding:
    contract = _contract()
    headers = contract["request"]["headers"]
    binding = EcrmInstallationBinding(
        workspace_id=headers["X-Workspace-Id"],
        ecrm_cell_id=headers["X-ECRM-Cell-Id"],
        ecrm_cell_key=headers["X-ECRM-Cell-Key"],
        base_url="https://cell.invalid",
        credential_secret_ref="secret-primary",
        capabilities=[contract["request"]["body"]["event_kind"]],
    )
    db.merge(binding)
    db.commit()
    monkeypatch.setenv("CONTRACT_ECRM_SECRET", "route-token")
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_ENDPOINTS",
        {
            "endpoint-primary": {
                "ecrm_cell_id": binding.ecrm_cell_id,
                "ecrm_cell_key": binding.ecrm_cell_key,
                "base_url": binding.base_url,
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_SECRET_REFERENCES",
        {
            "secret-primary": {
                "ecrm_cell_id": binding.ecrm_cell_id,
                "environment_name": "CONTRACT_ECRM_SECRET",
            }
        },
    )
    return binding


def test_ecrm_http_contract_ack_duplicate_conflict_and_identity_rejection(
    client: TestClient,
    db: Session,
    monkeypatch,
) -> None:
    contract = _contract()
    _configure_contract_binding(db, monkeypatch)
    route = contract["route"]
    headers = contract["request"]["headers"]
    body = contract["request"]["body"]

    first = client.post(route, headers=headers, json=body)
    duplicate = client.post(route, headers=headers, json=body)

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert duplicate.json() == first.json()
    assert first.json() == {
        **contract["acknowledgement"],
        "receipt_id": first.json()["receipt_id"],
    }
    conflict = client.post(
        route,
        headers=headers,
        json={**body, "payload": {"recordId": "changed"}},
    )
    assert conflict.status_code == 409

    for changed_header, changed_value in (
        ("Authorization", "Bearer wrong-token"),
        ("X-ECRM-Cell-Id", "cell-other"),
        ("X-ECRM-Cell-Key", "other-key"),
        ("X-Workspace-Id", "workspace-other"),
    ):
        rejected = client.post(
            route,
            headers={**headers, changed_header: changed_value},
            json={**body, "source_event_id": f"rejected-{changed_header}"},
        )
        assert rejected.status_code == 401


def test_workspace_admin_rotates_allowlisted_credential_and_old_ref_stops_use(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    suffix = uuid4().hex[:8]
    workspace_id = f"rotate-ws-{suffix}"
    cell_id = f"rotate-cell-{suffix}"
    cell_key = f"rotate-key-{suffix}"
    user = _workspace_admin(db, workspace_id)
    monkeypatch.setenv("ROTATE_SECRET_V1", "credential-v1")
    monkeypatch.setenv("ROTATE_SECRET_V2", "credential-v2")
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
            "secret-v1": {
                "ecrm_cell_id": cell_id,
                "environment_name": "ROTATE_SECRET_V1",
            },
            "secret-v2": {
                "ecrm_cell_id": cell_id,
                "environment_name": "ROTATE_SECRET_V2",
            },
        },
    )
    headers = {
        **superuser_token_headers,
        "X-Workspace-Id": workspace_id,
        "X-Correlation-Id": f"corr-{suffix}",
    }
    created = client.put(
        f"{settings.API_V1_STR}/ecrm-installations/binding",
        headers=headers,
        json={
            "endpoint_id": "endpoint-primary",
            "secret_reference_id": "secret-v1",
            "capabilities": ["WORKFLOW_EVENT"],
            "status": "ACTIVE",
            "source_version": 1,
        },
    )
    assert created.status_code == 200

    rotated = client.post(
        f"{settings.API_V1_STR}/ecrm-installations/binding/credential-rotations",
        headers=headers,
        json={"secret_reference_id": "secret-v2", "expected_source_version": 1},
    )

    assert rotated.status_code == 200
    assert rotated.json()["source_version"] == 2
    assert rotated.json()["rotated_at"] is not None
    binding = db.get(EcrmInstallationBinding, workspace_id)
    db.refresh(binding)
    assert binding.credential_secret_ref == "secret-v2"
    assert (
        db.exec(
            select(AuditEvent).where(
                AuditEvent.workspace_id == workspace_id,
                AuditEvent.event_name == "ecrm.installation.credential_rotated",
            )
        )
        .one()
        .actor_id
        == user.id
    )

    delivery_headers = {
        "X-ECRM-Cell-Id": cell_id,
        "X-ECRM-Cell-Key": cell_key,
        "X-Workspace-Id": workspace_id,
        "Idempotency-Key": f"rotation-{suffix}",
    }
    delivery_body = {
        "source_event_id": f"rotation-{suffix}",
        "source_version": 1,
        "stream_key": f"rotation:{suffix}",
        "event_kind": "WORKFLOW_EVENT",
        "payload": {},
    }
    assert (
        client.post(
            f"{settings.API_V1_STR}/ecrm-installations/deliveries",
            headers={**delivery_headers, "Authorization": "Bearer credential-v1"},
            json=delivery_body,
        ).status_code
        == 401
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/ecrm-installations/deliveries",
            headers={**delivery_headers, "Authorization": "Bearer credential-v2"},
            json=delivery_body,
        ).status_code
        == 202
    )


def test_rotation_compare_and_swap_rejects_stale_and_cross_cell_reference(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
    monkeypatch,
) -> None:
    suffix = uuid4().hex[:8]
    workspace_id = f"rotate-cas-{suffix}"
    cell_id = f"rotate-cas-cell-{suffix}"
    _workspace_admin(db, workspace_id)
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_ENDPOINTS",
        {
            "endpoint-primary": {
                "ecrm_cell_id": cell_id,
                "ecrm_cell_key": f"key-{suffix}",
                "base_url": "https://cell.invalid",
            }
        },
    )
    monkeypatch.setattr(
        settings,
        "ECRM_INSTALLATION_SECRET_REFERENCES",
        {
            "secret-v1": {"ecrm_cell_id": cell_id, "environment_name": "ROTATE_CAS_V1"},
            "secret-v2": {"ecrm_cell_id": cell_id, "environment_name": "ROTATE_CAS_V2"},
            "secret-other": {
                "ecrm_cell_id": "cell-other",
                "environment_name": "ROTATE_OTHER",
            },
        },
    )
    headers = {**superuser_token_headers, "X-Workspace-Id": workspace_id}
    assert (
        client.put(
            f"{settings.API_V1_STR}/ecrm-installations/binding",
            headers=headers,
            json={
                "endpoint_id": "endpoint-primary",
                "secret_reference_id": "secret-v1",
                "capabilities": ["WORKFLOW_EVENT"],
                "status": "ACTIVE",
                "source_version": 1,
            },
        ).status_code
        == 200
    )

    assert (
        client.post(
            f"{settings.API_V1_STR}/ecrm-installations/binding/credential-rotations",
            headers=headers,
            json={"secret_reference_id": "secret-other", "expected_source_version": 1},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{settings.API_V1_STR}/ecrm-installations/binding/credential-rotations",
            headers=headers,
            json={"secret_reference_id": "secret-v2", "expected_source_version": 1},
        ).status_code
        == 200
    )
    stale = client.post(
        f"{settings.API_V1_STR}/ecrm-installations/binding/credential-rotations",
        headers=headers,
        json={"secret_reference_id": "secret-v1", "expected_source_version": 1},
    )
    assert stale.status_code == 409
    binding = db.get(EcrmInstallationBinding, workspace_id)
    db.refresh(binding)
    assert (binding.credential_secret_ref, binding.source_version) == ("secret-v2", 2)


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
    assert (
        db.get(EcrmInstallationBinding, workspace_id).base_url == "https://cell.invalid"
    )


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
            "X-ECRM-Cell-Key": binding.ecrm_cell_key,
            "X-Workspace-Id": binding.workspace_id,
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
