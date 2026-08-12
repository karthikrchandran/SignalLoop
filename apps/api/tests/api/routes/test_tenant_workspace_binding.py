from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    Tenant,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace


def _tenant(prefix: str) -> Tenant:
    return Tenant(
        key=f"{prefix}-{uuid.uuid4().hex[:12]}",
        display_name=f"{prefix} tenant",
    )


def _installation(tenant: Tenant, workspace_id: str) -> ProductInstallation:
    return ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.SIGNAL_LOOP,
        local_identifier=workspace_id,
    )


def test_tenant_admin_provisions_verified_workspace_binding_with_audit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = _tenant("binding")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add(tenant)
    db.add(workspace)
    db.flush()
    installation = _installation(tenant, workspace.id)
    db.add(installation)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/installations/{installation.id}/workspace-binding",
        headers={**superuser_token_headers, "Idempotency-Key": "binding-create-v1"},
        json={"workspace_id": workspace.id, "status": "ACTIVE"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tenant_id": str(tenant.id),
        "installation_id": str(installation.id),
        "workspace_id": workspace.id,
        "status": "ACTIVE",
    }
    binding = db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == installation.id
        )
    ).one()
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.event_name == "tenant.workspace_binding.attested",
            AuditEvent.resource_id == str(binding.id),
        )
    ).one()
    assert audit.workspace_id == str(tenant.id)
    assert audit.payload == {"installation_id": str(installation.id), "status": "ACTIVE"}


def test_binding_rejects_workspace_that_is_not_the_installation_identifier(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = _tenant("mismatch")
    db.add(tenant)
    db.add(Workspace(id=f"ws-expected-{uuid.uuid4().hex[:8]}"))
    actual_workspace = Workspace(id=f"ws-other-{uuid.uuid4().hex[:8]}")
    db.add(actual_workspace)
    db.flush()
    installation = _installation(tenant, "ws-expected-not-matching")
    db.add(installation)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/installations/{installation.id}/workspace-binding",
        headers={**superuser_token_headers, "Idempotency-Key": "binding-mismatch-v1"},
        json={"workspace_id": actual_workspace.id, "status": "ACTIVE"},
    )

    assert response.status_code == 409
    assert db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == installation.id
        )
    ).one_or_none() is None


def test_binding_does_not_disclose_or_bind_another_tenants_installation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = _tenant("one")
    other_tenant = _tenant("two")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add(tenant)
    db.add(other_tenant)
    db.add(workspace)
    db.flush()
    other_installation = _installation(other_tenant, workspace.id)
    db.add(other_installation)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/installations/{other_installation.id}/workspace-binding",
        headers={**superuser_token_headers, "Idempotency-Key": "binding-cross-tenant-v1"},
        json={"workspace_id": workspace.id, "status": "ACTIVE"},
    )

    assert response.status_code == 404
    assert db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == other_installation.id
        )
    ).one_or_none() is None


def test_binding_rejects_a_workspace_already_attested_to_another_installation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    first_tenant = _tenant("first")
    second_tenant = _tenant("second")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add(first_tenant)
    db.add(second_tenant)
    db.add(workspace)
    db.flush()
    first_installation = _installation(first_tenant, workspace.id)
    second_installation = _installation(second_tenant, workspace.id)
    db.add(first_installation)
    db.add(second_installation)
    db.flush()
    db.add(
        TenantWorkspaceBinding(
            tenant_id=first_tenant.id,
            installation_id=first_installation.id,
            workspace_id=workspace.id,
        )
    )
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/tenant-admin/tenants/{second_tenant.id}/installations/{second_installation.id}/workspace-binding",
        headers={**superuser_token_headers, "Idempotency-Key": "binding-duplicate-v1"},
        json={"workspace_id": workspace.id, "status": "ACTIVE"},
    )

    assert response.status_code == 409
    assert db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == second_installation.id
        )
    ).one_or_none() is None


def test_binding_can_suspend_the_existing_verified_relationship_idempotently(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = _tenant("suspend")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add(tenant)
    db.add(workspace)
    db.flush()
    installation = _installation(tenant, workspace.id)
    db.add(installation)
    db.flush()
    binding = TenantWorkspaceBinding(
        tenant_id=tenant.id,
        installation_id=installation.id,
        workspace_id=workspace.id,
    )
    db.add(binding)
    db.commit()

    url = f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/installations/{installation.id}/workspace-binding"
    headers = {**superuser_token_headers, "Idempotency-Key": "binding-suspend-v1"}
    first = client.put(url, headers=headers, json={"workspace_id": workspace.id, "status": "SUSPENDED"})
    replay = client.put(url, headers=headers, json={"workspace_id": workspace.id, "status": "SUSPENDED"})

    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json() == first.json()
    db.expire_all()
    assert db.get(TenantWorkspaceBinding, binding.id).status == "SUSPENDED"
