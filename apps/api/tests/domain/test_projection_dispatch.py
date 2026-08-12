from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from app.domain.installations.projection_dispatch import (
    acknowledge_projection_event,
    dispatch_projection_events,
    enqueue_projection_event,
    reconcile_projection_status,
)
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _installation(session: Session) -> ProductInstallation:
    tenant = Tenant(key="tenant-a", display_name="Tenant A")
    session.add(tenant)
    session.commit()
    installation = ProductInstallation(
        tenant_id=tenant.id,
        product_code=ProductCode.REVENUE_OS,
        local_identifier="revenueos-a",
    )
    session.add(installation)
    session.commit()
    session.refresh(installation)
    return installation


def test_enqueue_is_idempotent_per_installation_and_dispatch_acknowledges() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={"user_id": "u1", "role": "EMPLOYEE"},
            idempotency_key="membership-u1-v1",
        )
        duplicate = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={"user_id": "u1", "role": "EMPLOYEE"},
            idempotency_key="membership-u1-v1",
        )
        assert event.id == duplicate.id
        applied: list[dict[str, object]] = []

        dispatched = dispatch_projection_events(
            session,
            installation_id=installation.id,
            apply=lambda item: applied.append(item.payload),
        )

        assert dispatched == 1
        assert applied == [{"user_id": "u1", "role": "EMPLOYEE"}]
        status = reconcile_projection_status(session, installation_id=installation.id)
        assert status.acknowledged == 1
        assert status.pending == 0
        assert status.dead_letter == 0


def test_dispatch_retries_then_dead_letters_and_can_be_reconciled() -> None:
    with _session() as session:
        installation = _installation(session)
        enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="entitlement.changed",
            payload={"product": "signalloop", "status": "ACTIVE"},
            idempotency_key="entitlement-v1",
        )
        now = datetime.now(timezone.utc)
        for attempt in range(3):
            assert dispatch_projection_events(
                session,
                installation_id=installation.id,
                apply=lambda _item: (_ for _ in ()).throw(RuntimeError("native unavailable")),
                max_attempts=3,
                now=now + timedelta(seconds=attempt + 1),
            ) == 0

        status = reconcile_projection_status(session, installation_id=installation.id)
        assert status.pending == 0
        assert status.dead_letter == 1
        assert status.last_error == "native unavailable"


def test_acknowledgement_is_idempotent_and_rejects_wrong_installation() -> None:
    with _session() as session:
        installation = _installation(session)
        other = ProductInstallation(
            tenant_id=installation.tenant_id,
            product_code=ProductCode.SIGNAL_LOOP,
            local_identifier="signalloop-a",
        )
        session.add(other)
        session.commit()
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="branding.published",
            payload={"version": 2},
            idempotency_key="branding-v2",
        )
        assert acknowledge_projection_event(
            session,
            installation_id=other.id,
            event_id=event.id,
            payload_digest="x" * 64,
        ) is False
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest="x" * 64,
        ) is True
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest="x" * 64,
        ) is True
