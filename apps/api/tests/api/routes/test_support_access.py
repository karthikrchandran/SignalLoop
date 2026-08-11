from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import crud
from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.tenants.models import SupportAccessGrant, Tenant, utc_now
from app.models import UserCreate
from tests.utils.shared_records import install_shared_record_mocks
from tests.utils.user import user_authentication_headers


@pytest.fixture(autouse=True)
def clear_support_grants(db: Session) -> None:
    yield
    db.rollback()
    db.exec(delete(SupportAccessGrant))
    db.commit()


def _operator_headers(client: TestClient, db: Session) -> tuple[str, dict[str, str]]:
    email = f"platform-support-{uuid.uuid4().hex[:8]}@example.com"
    password = "support-test-password"
    operator = crud.create_user(
        session=db,
        user_create=UserCreate(email=email, password=password),
    )
    operator.role = "admin"
    db.add(operator)
    db.commit()
    return str(operator.id), user_authentication_headers(client=client, email=email, password=password)


def test_live_tenant_support_grant_allows_contact_read_and_audits_use(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_shared_record_mocks(monkeypatch)
    operator_id, headers = _operator_headers(client, db)
    workspace_id = f"ara-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(key=workspace_id, display_name="ARA")
    db.add(tenant)
    db.flush()
    grant = SupportAccessGrant(
        tenant_id=tenant.id,
        operator_user_id=uuid.UUID(operator_id),
        capabilities=["contacts.read"],
        reason="Investigating SUP-123",
        approved_by=uuid.UUID(operator_id),
        expires_at=utc_now() + timedelta(hours=1),
    )
    db.add(grant)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/contacts/",
        headers={
            **headers,
            "X-Workspace-Id": workspace_id,
            "X-Support-Grant-Id": str(grant.id),
        },
    )

    assert response.status_code == 200
    events = db.exec(
        select(AuditEvent.event_name).where(AuditEvent.resource_id == str(grant.id))
    ).all()
    assert "support.grant.used" in events


def test_expired_tenant_support_grant_is_hidden_and_audited(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_shared_record_mocks(monkeypatch)
    operator_id, headers = _operator_headers(client, db)
    workspace_id = f"ara-{uuid.uuid4().hex[:8]}"
    tenant = Tenant(key=workspace_id, display_name="ARA")
    db.add(tenant)
    db.flush()
    grant = SupportAccessGrant(
        tenant_id=tenant.id,
        operator_user_id=uuid.UUID(operator_id),
        capabilities=["contacts.read"],
        reason="Investigating SUP-123",
        approved_by=uuid.UUID(operator_id),
        expires_at=utc_now() - timedelta(minutes=1),
    )
    db.add(grant)
    db.commit()

    response = client.get(
        f"{settings.API_V1_STR}/contacts/",
        headers={
            **headers,
            "X-Workspace-Id": workspace_id,
            "X-Support-Grant-Id": str(grant.id),
        },
    )

    assert response.status_code == 404
    events = db.exec(
        select(AuditEvent).where(AuditEvent.resource_id == str(grant.id))
    ).all()
    assert any(event.payload.get("denial_reason") == "SUPPORT_GRANT_EXPIRED" for event in events)
