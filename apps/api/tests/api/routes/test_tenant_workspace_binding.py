from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.routes.tenant_admin import (
    TenantWorkspaceBindingChange,
    _attest_workspace_binding_once,
)
from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    Tenant,
    TenantEntitlement,
    TenantWorkspaceBinding,
)
from app.domain.workspaces.models import Workspace
from app.models import User
from tests.utils.user import authentication_token_from_email


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


def _tenant_user_headers(
    client: TestClient,
    db: Session,
    tenant: Tenant,
    role: RoleBundle,
) -> dict[str, str]:
    email = f"binding-{uuid.uuid4().hex}@example.com"
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = db.exec(select(User).where(User.email == email)).one()
    membership = SuiteMembership(tenant_id=tenant.id, user_id=user.id)
    db.add(membership)
    db.flush()
    db.add(SuiteRoleAssignment(membership_id=membership.id, role_bundle=role))
    db.commit()
    return headers


def _binding_url(tenant: Tenant, installation: ProductInstallation) -> str:
    return (
        f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}"
        f"/installations/{installation.id}/workspace-binding"
    )


def _audit_events(db: Session, installation: ProductInstallation) -> list[AuditEvent]:
    return [
        event
        for event in db.exec(
            select(AuditEvent).where(
                AuditEvent.event_name == "tenant.workspace_binding.attested"
            )
        ).all()
        if event.payload.get("installation_id") == str(installation.id)
    ]


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


def test_active_tenant_owner_can_attest_but_member_without_capability_is_denied(
    client: TestClient,
    db: Session,
) -> None:
    tenant = _tenant("owner-auth")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add_all(
        [
            tenant,
            workspace,
            TenantEntitlement(
                tenant_id=tenant.id,
                product_code=ProductCode.SIGNAL_LOOP,
            ),
        ]
    )
    db.flush()
    installation = _installation(tenant, workspace.id)
    db.add(installation)
    db.commit()

    owner_headers = _tenant_user_headers(client, db, tenant, RoleBundle.TENANT_OWNER)
    member_headers = _tenant_user_headers(client, db, tenant, RoleBundle.EMPLOYEE)
    url = _binding_url(tenant, installation)

    owner_response = client.put(
        url,
        headers={**owner_headers, "Idempotency-Key": "owner-binding-v1"},
        json={"workspace_id": workspace.id, "status": "ACTIVE"},
    )
    member_response = client.put(
        url,
        headers={**member_headers, "Idempotency-Key": "member-binding-v1"},
        json={"workspace_id": workspace.id, "status": "SUSPENDED"},
    )

    assert owner_response.status_code == 200
    assert member_response.status_code == 403
    db.expire_all()
    assert db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == installation.id
        )
    ).one().status == "ACTIVE"


def test_changed_payload_for_workspace_binding_key_conflicts_without_extra_mutation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = _tenant("binding-key-conflict")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    db.add_all([tenant, workspace])
    db.flush()
    installation = _installation(tenant, workspace.id)
    db.add(installation)
    db.commit()

    url = _binding_url(tenant, installation)
    headers = {**superuser_token_headers, "Idempotency-Key": "binding-key-reuse-v1"}
    created = client.put(
        url,
        headers=headers,
        json={"workspace_id": workspace.id, "status": "ACTIVE"},
    )
    conflict = client.put(
        url,
        headers=headers,
        json={"workspace_id": workspace.id, "status": "SUSPENDED"},
    )

    assert created.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    db.expire_all()
    binding = db.exec(
        select(TenantWorkspaceBinding).where(
            TenantWorkspaceBinding.installation_id == installation.id
        )
    ).one()
    assert binding.status == "ACTIVE"
    assert len(_audit_events(db, installation)) == 1


def test_forced_two_session_binding_race_returns_one_success_and_one_conflict(
    tmp_path,
) -> None:
    """Two SQLite connections cross the unique-binding boundary together."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'binding-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Tenant.__table__,
            ProductInstallation.__table__,
            Workspace.__table__,
            TenantWorkspaceBinding.__table__,
            AuditEvent.__table__,
        ],
    )
    tenant = _tenant("forced-binding-race")
    workspace = Workspace(id=f"ws-{uuid.uuid4().hex[:12]}")
    workspace_id = workspace.id
    actor = User(email=f"binding-{uuid.uuid4().hex}@example.com", hashed_password="test")
    with Session(engine) as setup:
        setup.add_all([tenant, workspace, actor])
        setup.flush()
        installation = _installation(tenant, workspace_id)
        setup.add(installation)
        setup.commit()
        tenant_id, installation_id, actor_id = tenant.id, installation.id, actor.id

    barrier = Barrier(2)
    first, second = Session(engine), Session(engine)
    original_begin_nested = Session.begin_nested

    @contextmanager
    def synchronized_begin_nested(session: Session):
        barrier.wait(timeout=10)
        with original_begin_nested(session) as transaction:
            yield transaction

    def attempt_status(session: Session) -> int:
        try:
            actor_for_attempt = session.get(User, actor_id)
            tenant_for_attempt = session.get(Tenant, tenant_id)
            installation_for_attempt = session.get(ProductInstallation, installation_id)
            assert actor_for_attempt and tenant_for_attempt and installation_for_attempt
            _attest_workspace_binding_once(
                session=session,
                user=actor_for_attempt,
                tenant=tenant_for_attempt,
                installation=installation_for_attempt,
                payload=TenantWorkspaceBindingChange(workspace_id=workspace_id),
            )
            return 200
        except HTTPException as exc:
            return exc.status_code

    try:
        with patch.object(Session, "begin_nested", synchronized_begin_nested):
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(attempt_status, (first, second)))
    finally:
        first.close()
        second.close()

    assert sorted(statuses) == [200, 409]
    with Session(engine) as verify:
        assert len(verify.exec(select(TenantWorkspaceBinding)).all()) == 1
        assert len(_audit_events(verify, installation)) == 1
