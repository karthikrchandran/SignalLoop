from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine

from app.domain.installations.projection_dispatch import enqueue_projection_event
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.workers.projection_worker import ProjectionWorker


def test_worker_only_processes_active_revenueos_installations_for_active_tenants() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        active = Tenant(key="active", display_name="Active")
        suspended = Tenant(key="suspended", display_name="Suspended", status="SUSPENDED")
        session.add(active)
        session.add(suspended)
        session.commit()
        revenueos = ProductInstallation(
            tenant_id=active.id, product_code=ProductCode.REVENUE_OS, local_identifier="r"
        )
        signalloop = ProductInstallation(
            tenant_id=active.id, product_code=ProductCode.SIGNAL_LOOP, local_identifier="s"
        )
        suspended_revenueos = ProductInstallation(
            tenant_id=suspended.id, product_code=ProductCode.REVENUE_OS, local_identifier="sr"
        )
        session.add(revenueos)
        session.add(signalloop)
        session.add(suspended_revenueos)
        session.commit()
        for installation in (revenueos, signalloop, suspended_revenueos):
            enqueue_projection_event(
                session,
                installation_id=installation.id,
                tenant_id=installation.tenant_id,
                event_type="membership.changed",
                payload={"installation": installation.local_identifier},
                idempotency_key=installation.local_identifier,
            )
        applied: list[str] = []
        assert ProjectionWorker(lambda event: applied.append(event.payload["installation"])).run_once(session) == 1
        assert applied == ["r"]
