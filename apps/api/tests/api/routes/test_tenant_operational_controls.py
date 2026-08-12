from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.tenants.models import ProductCode, Tenant, TenantOperationalControl


def test_platform_admin_pauses_one_tenant_product_with_auditable_reason(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = Tenant(
        key=f"operations-{uuid.uuid4().hex[:12]}",
        display_name="Operations test tenant",
    )
    db.add(tenant)
    db.commit()

    response = client.put(
        f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/operations/revenueos/control",
        headers=superuser_token_headers,
        json={"paused": True, "reason": "provider incident INC-42"},
    )

    assert response.status_code == 200
    assert response.json()["paused"] is True
    assert response.json()["product_code"] == "revenueos"
    control = db.exec(
        select(TenantOperationalControl).where(
            TenantOperationalControl.tenant_id == tenant.id,
            TenantOperationalControl.product_code == ProductCode.REVENUE_OS,
        )
    ).one()
    assert control.paused_reason == "provider incident INC-42"
    audit = db.exec(
        select(AuditEvent).where(
            AuditEvent.event_name == "tenant.operational_control.changed",
            AuditEvent.resource_id == str(control.id),
        )
    ).one()
    assert audit.payload["paused"] is True
