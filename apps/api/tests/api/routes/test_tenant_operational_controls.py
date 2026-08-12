from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor

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


def test_concurrent_first_control_writes_upsert_one_row_without_server_error(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    tenant = Tenant(
        key=f"operations-race-{uuid.uuid4().hex[:10]}",
        display_name="Concurrent operations test tenant",
    )
    db.add(tenant)
    db.commit()
    url = f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/operations/revenueos/control"

    def write_control(reason: str) -> int:
        return client.put(
            url,
            headers=superuser_token_headers,
            json={"paused": True, "reason": reason},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(write_control, ("incident one", "incident two")))

    db.expire_all()
    rows = db.exec(
        select(TenantOperationalControl).where(
            TenantOperationalControl.tenant_id == tenant.id,
            TenantOperationalControl.product_code == ProductCode.REVENUE_OS,
        )
    ).all()
    assert statuses == [200, 200]
    assert len(rows) == 1
