from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.tenants.models import SupportAccessGrant, Tenant, utc_now
from app.models import User


@pytest.fixture(autouse=True)
def clear_support_grants(db: Session) -> None:
    yield
    db.rollback()
    db.execute(delete(SupportAccessGrant))
    db.commit()


def test_platform_admin_issues_and_revokes_a_reasoned_support_grant(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    tenant = Tenant(key=f"ara-{uuid.uuid4().hex[:8]}", display_name="ARA")
    operator = User(
        email=f"support-{uuid.uuid4().hex[:8]}@example.test",
        hashed_password="not-used",
        is_superuser=True,
    )
    db.add_all([tenant, operator])
    db.commit()

    issued = client.post(
        f"{settings.API_V1_STR}/platform-admin/support-grants",
        headers=superuser_token_headers,
        json={
            "tenant_id": str(tenant.id),
            "operator_user_id": str(operator.id),
            "capabilities": ["contacts.read"],
            "reason": "Investigating SUP-123",
            "ticket_reference": "SUP-123",
            "expires_at": (utc_now() + timedelta(hours=1)).isoformat(),
        },
    )

    assert issued.status_code == 201
    grant_id = issued.json()["id"]
    assert issued.json()["approved_by"]

    revoked = client.post(
        f"{settings.API_V1_STR}/platform-admin/support-grants/{grant_id}/revoke",
        headers=superuser_token_headers,
    )

    assert revoked.status_code == 200
    grant = db.get(SupportAccessGrant, uuid.UUID(grant_id))
    assert grant is not None and grant.revoked_at is not None
    events = db.exec(
        select(AuditEvent.event_name).where(AuditEvent.resource_id == grant_id)
    ).all()
    assert events == ["support.grant.issued", "support.grant.revoked"]
