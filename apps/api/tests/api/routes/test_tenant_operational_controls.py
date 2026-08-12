from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain.audit.audit_events import AuditEvent
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore
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


def test_pause_serializes_with_a_claim_and_blocks_later_claims(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    """A claim holding the tenant lock is pre-pause; later pending work is blocked."""
    tenant = Tenant(
        key=f"operations-lock-{uuid.uuid4().hex[:10]}",
        display_name="Lock sequencing tenant",
    )
    db.add(tenant)
    db.commit()

    lock_acquired = Event()
    release_claim = Event()

    def claim_one() -> bool:
        with Session(engine) as claim_session:
            store = RevenueInterventionStore(claim_session)
            allowed = store._tenant_execution_claim_allowed(
                tenant.id,
                after_tenant_lock=lambda: (
                    lock_acquired.set(),
                    release_claim.wait(timeout=5),
                ),
            )
            claim_session.commit()
            return allowed

    control_url = f"{settings.API_V1_STR}/tenant-admin/tenants/{tenant.id}/operations/revenueos/control"
    with ThreadPoolExecutor(max_workers=2) as executor:
        claim_future = executor.submit(claim_one)
        assert lock_acquired.wait(timeout=5)
        pause_future = executor.submit(
            client.put,
            control_url,
            headers=superuser_token_headers,
            json={"paused": True, "reason": "deterministic lock test"},
        )
        assert not pause_future.done()
        release_claim.set()
        claim_allowed = claim_future.result(timeout=5)
        pause_response = pause_future.result(timeout=5)

    assert claim_allowed is True
    assert pause_response.status_code == 200
    with Session(engine) as verification_session:
        assert not RevenueInterventionStore(
            verification_session
        )._tenant_execution_claim_allowed(tenant.id)
