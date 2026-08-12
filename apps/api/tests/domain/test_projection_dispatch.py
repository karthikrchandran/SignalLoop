from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.installations.projection_dispatch import (
    acknowledge_projection_event,
    claim_projection_event,
    dispatch_projection_events,
    enqueue_projection_event,
    reconcile_projection_status,
    record_projection_failure,
    repair_projection_events,
    replay_dead_letter_projection_event,
)
from app.domain.tenants.models import (
    NativeProjectionReceipt,
    ProductCode,
    ProductInstallation,
    Tenant,
)


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


def _digest(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
        for offset in (1, 2, 4):
            assert dispatch_projection_events(
                session,
                installation_id=installation.id,
                apply=lambda _item: (_ for _ in ()).throw(RuntimeError("native unavailable")),
                max_attempts=3,
                now=now + timedelta(seconds=offset),
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
            payload_digest=_digest(event.payload),
            lease_token=uuid.uuid4(),
        ) is False
        lease_token = claim_projection_event(
            session, installation_id=installation.id, event_id=event.id
        )
        assert lease_token is not None
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest=_digest(event.payload),
            lease_token=lease_token,
        ) is True
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest=_digest(event.payload),
            lease_token=lease_token,
        ) is True


def test_enqueue_rejects_tenant_that_does_not_own_installation() -> None:
    with _session() as session:
        installation = _installation(session)
        other_tenant = Tenant(key="tenant-b", display_name="Tenant B")
        session.add(other_tenant)
        session.commit()

        with pytest.raises(ValueError, match="does not own installation"):
            enqueue_projection_event(
                session,
                installation_id=installation.id,
                tenant_id=other_tenant.id,
                event_type="membership.changed",
                payload={},
                idempotency_key="cross-tenant",
            )


def test_dispatch_claim_prevents_a_second_worker_from_applying_an_in_progress_event() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={"user_id": "u1"},
            idempotency_key="claim-v1",
        )
        event.status = "IN_PROGRESS"
        event.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
        session.add(event)
        session.commit()
        applied: list[str] = []

        assert dispatch_projection_events(
            session,
            installation_id=installation.id,
            apply=lambda item: applied.append(item.event_type),
        ) == 0
        assert applied == []


def test_acknowledgement_rejects_a_digest_that_does_not_match_the_queued_payload() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="branding.published",
            payload={"version": 2},
            idempotency_key="branding-digest",
        )

        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest="x" * 64,
            lease_token=uuid.uuid4(),
        ) is False
        assert reconcile_projection_status(session, installation_id=installation.id).pending == 1


def test_reconciliation_reports_bad_receipts_and_repairs_expired_claims() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="entitlement.changed",
            payload={"status": "ACTIVE"},
            idempotency_key="repair-v1",
        )
        event.status = "IN_PROGRESS"
        event.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(event)
        session.commit()

        status = reconcile_projection_status(session, installation_id=installation.id)
        assert status.integrity_issues == 1
        assert status.repairable == 1
        assert repair_projection_events(session, installation_id=installation.id) == 1
        assert reconcile_projection_status(session, installation_id=installation.id).pending == 1

        event.status = "ACKNOWLEDGED"
        session.add(event)
        session.add(
            NativeProjectionReceipt(
                installation_id=installation.id,
                event_id=event.id,
                payload_digest="wrong",
            )
        )
        session.commit()
        assert reconcile_projection_status(session, installation_id=installation.id).integrity_issues == 1


def test_failed_dispatch_uses_backoff_and_dead_letter_replay_is_explicit() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="entitlement.changed",
            payload={},
            idempotency_key="retry-v1",
        )
        now = datetime.now(timezone.utc)
        def failure(_item: object) -> None:
            raise RuntimeError("unavailable")
        assert dispatch_projection_events(
            session, installation_id=installation.id, apply=failure, max_attempts=2, now=now
        ) == 0
        session.refresh(event)
        assert event.status == "PENDING"
        assert event.available_at.replace(tzinfo=timezone.utc) == now + timedelta(seconds=1)
        assert dispatch_projection_events(
            session, installation_id=installation.id, apply=failure, max_attempts=2, now=now
        ) == 0
        assert dispatch_projection_events(
            session,
            installation_id=installation.id,
            apply=failure,
            max_attempts=2,
            now=now + timedelta(seconds=1),
        ) == 0
        session.refresh(event)
        assert event.status == "DEAD_LETTER"

        assert replay_dead_letter_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            actor_id=uuid.uuid4(),
            actor_role="REVENUE_OS_ADMIN",
            now=now + timedelta(seconds=2),
        ) is True
        session.refresh(event)
        assert event.status == "PENDING"
        assert event.attempt_count == 0


def test_stale_dispatcher_cannot_acknowledge_or_fail_a_reclaimed_lease() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={"user_id": "u1"},
            idempotency_key="lease-race-v1",
        )
        first_lease = claim_projection_event(
            session, installation_id=installation.id, event_id=event.id
        )
        assert first_lease is not None
        event.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(event)
        session.commit()
        assert repair_projection_events(session, installation_id=installation.id) == 1
        second_lease = claim_projection_event(
            session, installation_id=installation.id, event_id=event.id
        )
        assert second_lease is not None and second_lease != first_lease
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest=_digest(event.payload),
            lease_token=first_lease,
        ) is False
        assert record_projection_failure(
            session,
            installation_id=installation.id,
            event_id=event.id,
            lease_token=first_lease,
            error=RuntimeError("late failure"),
            max_attempts=3,
        ) is False
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest=_digest(event.payload),
            lease_token=second_lease,
        ) is True


def test_repair_requeues_acknowledged_event_with_missing_or_corrupt_receipt() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={},
            idempotency_key="receipt-repair-v1",
        )
        event.status = "ACKNOWLEDGED"
        session.add(event)
        session.commit()
        assert repair_projection_events(session, installation_id=installation.id) == 1
        session.refresh(event)
        assert event.status == "PENDING"


def test_interleaved_lease_completion_allows_only_the_current_owner_to_transition() -> None:
    with _session() as session:
        installation = _installation(session)
        event = enqueue_projection_event(
            session,
            installation_id=installation.id,
            tenant_id=installation.tenant_id,
            event_type="membership.changed",
            payload={},
            idempotency_key="atomic-race-v1",
        )
        first = claim_projection_event(session, installation_id=installation.id, event_id=event.id)
        assert first is not None
        event.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.add(event)
        session.commit()
        assert repair_projection_events(session, installation_id=installation.id) == 1
        second = claim_projection_event(session, installation_id=installation.id, event_id=event.id)
        assert second is not None
        assert record_projection_failure(
            session,
            installation_id=installation.id,
            event_id=event.id,
            lease_token=first,
            error=RuntimeError("late"),
            max_attempts=3,
        ) is False
        assert acknowledge_projection_event(
            session,
            installation_id=installation.id,
            event_id=event.id,
            payload_digest=_digest(event.payload),
            lease_token=second,
        ) is True
