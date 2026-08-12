"""Durable dispatch and reconciliation for native product projections."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from sqlalchemy import desc, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.tenants.models import (
    NativeProjectionReceipt,
    ProductInstallation,
    ProjectionDispatchEvent,
)

_EVENT_TABLE = cast(Any, ProjectionDispatchEvent.__table__)  # type: ignore[attr-defined]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _payload_digest(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProjectionReconciliationStatus:
    pending: int
    acknowledged: int
    dead_letter: int
    last_error: str | None
    integrity_issues: int
    repairable: int


def enqueue_projection_event(
    session: Session,
    *,
    installation_id: uuid.UUID,
    tenant_id: uuid.UUID,
    event_type: str,
    payload: dict[str, object],
    idempotency_key: str,
) -> ProjectionDispatchEvent:
    """Persist one projection event, returning the original for duplicate requests."""

    installation = session.get(ProductInstallation, installation_id)
    if installation is None:
        raise ValueError("installation does not exist")
    if installation.tenant_id != tenant_id:
        raise ValueError("tenant does not own installation")

    existing = session.exec(
        select(ProjectionDispatchEvent).where(
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.idempotency_key == idempotency_key,
        )
    ).first()
    if existing is not None:
        return existing

    event = ProjectionDispatchEvent(
        installation_id=installation_id,
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        duplicate = session.exec(
            select(ProjectionDispatchEvent).where(
                ProjectionDispatchEvent.installation_id == installation_id,
                ProjectionDispatchEvent.idempotency_key == idempotency_key,
            )
        ).first()
        if duplicate is None:
            raise
        return duplicate
    session.refresh(event)
    return event


def acknowledge_projection_event(
    session: Session,
    *,
    installation_id: uuid.UUID,
    event_id: uuid.UUID,
    payload_digest: str,
    lease_token: uuid.UUID,
    now: datetime | None = None,
) -> bool:
    """Acknowledge an installation-owned event exactly once, safely on replay."""

    event = session.exec(
        select(ProjectionDispatchEvent).where(
            ProjectionDispatchEvent.id == event_id,
            ProjectionDispatchEvent.installation_id == installation_id,
        )
    ).first()
    if event is None:
        return False
    if event.status == "ACKNOWLEDGED":
        receipt = session.exec(
            select(NativeProjectionReceipt).where(
                NativeProjectionReceipt.installation_id == installation_id,
                NativeProjectionReceipt.event_id == event_id,
            )
        ).first()
        return receipt is not None and receipt.payload_digest == payload_digest
    if payload_digest != _payload_digest(event.payload):
        return False

    receipt = session.exec(
        select(NativeProjectionReceipt).where(
            NativeProjectionReceipt.installation_id == installation_id,
            NativeProjectionReceipt.event_id == event_id,
        )
    ).first()
    if receipt is not None and receipt.payload_digest != payload_digest:
        return False
    timestamp = now or _now()
    transition = session.exec(
        update(ProjectionDispatchEvent)
        .where(
            _EVENT_TABLE.c.id == event_id,
            _EVENT_TABLE.c.installation_id == installation_id,
            _EVENT_TABLE.c.status == "IN_PROGRESS",
            _EVENT_TABLE.c.lease_token == lease_token,
            _EVENT_TABLE.c.lease_expires_at >= timestamp,
        )
        .values(
            status="ACKNOWLEDGED",
            acknowledged_at=timestamp,
            last_error=None,
            lease_token=None,
            lease_expires_at=None,
            updated_at=timestamp,
        )
        .execution_options(synchronize_session=False)
    )
    if transition.rowcount != 1:
        session.rollback()
        return False
    if receipt is None:
        receipt = NativeProjectionReceipt(
            installation_id=installation_id,
            event_id=event_id,
            payload_digest=payload_digest,
            acknowledged_at=timestamp,
        )
        session.add(receipt)

    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        repaired = session.exec(
            select(NativeProjectionReceipt).where(
                NativeProjectionReceipt.installation_id == installation_id,
                NativeProjectionReceipt.event_id == event_id,
            )
        ).first()
        return repaired is not None and repaired.payload_digest == payload_digest
    return True


def claim_projection_event(
    session: Session,
    *,
    installation_id: uuid.UUID,
    event_id: uuid.UUID,
    now: datetime | None = None,
) -> uuid.UUID | None:
    """Atomically lease due work to a dispatcher, returning its ownership token."""

    timestamp = now or _now()
    lease_token = uuid.uuid4()
    claim = session.exec(
        update(ProjectionDispatchEvent)
        .where(
            _EVENT_TABLE.c.id == event_id,
            _EVENT_TABLE.c.installation_id == installation_id,
            _EVENT_TABLE.c.status == "PENDING",
            _EVENT_TABLE.c.available_at <= timestamp,
        )
        .values(
            status="IN_PROGRESS",
            lease_token=lease_token,
            lease_expires_at=timestamp + timedelta(minutes=5),
            updated_at=timestamp,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return lease_token if claim.rowcount == 1 else None


def record_projection_failure(
    session: Session,
    *,
    installation_id: uuid.UUID,
    event_id: uuid.UUID,
    lease_token: uuid.UUID,
    error: Exception,
    max_attempts: int,
    now: datetime | None = None,
) -> bool:
    """Release/retry a lease only when the caller still owns that exact lease."""

    timestamp = now or _now()
    event = session.exec(
        select(ProjectionDispatchEvent).where(
            ProjectionDispatchEvent.id == event_id,
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.status == "IN_PROGRESS",
            ProjectionDispatchEvent.lease_token == lease_token,
        )
    ).first()
    if event is None:
        return False
    attempt_count = event.attempt_count + 1
    values: dict[str, object] = {
        "attempt_count": attempt_count,
        "last_error": str(error)[:500],
        "updated_at": timestamp,
        "lease_token": None,
        "lease_expires_at": None,
    }
    if attempt_count >= max_attempts:
        values.update(status="DEAD_LETTER", dead_lettered_at=timestamp)
    else:
        values.update(
            status="PENDING",
            available_at=timestamp + timedelta(seconds=2 ** (attempt_count - 1)),
        )
    transition = session.exec(
        update(ProjectionDispatchEvent)
        .where(
            _EVENT_TABLE.c.id == event_id,
            _EVENT_TABLE.c.installation_id == installation_id,
            _EVENT_TABLE.c.status == "IN_PROGRESS",
            _EVENT_TABLE.c.lease_token == lease_token,
            _EVENT_TABLE.c.lease_expires_at >= timestamp,
        )
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    session.commit()
    return transition.rowcount == 1


def dispatch_projection_events(
    session: Session,
    *,
    installation_id: uuid.UUID,
    apply: Callable[[ProjectionDispatchEvent], object],
    max_attempts: int = 3,
    now: datetime | None = None,
) -> int:
    """Apply pending events, retaining failures until their retry budget is exhausted."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")

    timestamp = now or _now()
    event_ids = session.exec(
        select(ProjectionDispatchEvent.id)
        .where(
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.status == "PENDING",
            ProjectionDispatchEvent.available_at <= timestamp,
        )
        .order_by("created_at")
    ).all()
    dispatched = 0
    for event_id in event_ids:
        lease_token = claim_projection_event(
            session, installation_id=installation_id, event_id=event_id, now=timestamp
        )
        if lease_token is None:
            continue
        event = session.get(ProjectionDispatchEvent, event_id)
        if event is None:
            continue
        try:
            apply(event)
        except Exception as error:
            record_projection_failure(
                session,
                installation_id=installation_id,
                event_id=event.id,
                lease_token=lease_token,
                error=error,
                max_attempts=max_attempts,
                now=timestamp,
            )
            continue

        if acknowledge_projection_event(
            session,
            installation_id=installation_id,
            event_id=event.id,
            payload_digest=_payload_digest(event.payload),
            lease_token=lease_token,
            now=timestamp,
        ):
            dispatched += 1
    return dispatched


def reconcile_projection_status(
    session: Session, *, installation_id: uuid.UUID
) -> ProjectionReconciliationStatus:
    """Report durable projection queue state for the installation control plane."""

    events = session.exec(
        select(ProjectionDispatchEvent)
        .where(ProjectionDispatchEvent.installation_id == installation_id)
        .order_by(desc("updated_at"))
    ).all()
    receipts = {
        receipt.event_id: receipt
        for receipt in session.exec(
            select(NativeProjectionReceipt).where(
                NativeProjectionReceipt.installation_id == installation_id
            )
        ).all()
    }
    now = _now()
    integrity_issues = 0
    repairable = 0
    for event in events:
        receipt = receipts.get(event.id)
        if event.status == "ACKNOWLEDGED" and (
            receipt is None or receipt.payload_digest != _payload_digest(event.payload)
        ):
            integrity_issues += 1
            repairable += 1
        if event.status == "IN_PROGRESS" and (
            event.lease_expires_at is None or _as_utc(event.lease_expires_at) <= now
        ):
            integrity_issues += 1
            repairable += 1

    return ProjectionReconciliationStatus(
        pending=sum(event.status == "PENDING" for event in events),
        acknowledged=sum(event.status == "ACKNOWLEDGED" for event in events),
        dead_letter=sum(event.status == "DEAD_LETTER" for event in events),
        last_error=next(
            (event.last_error for event in events if event.last_error is not None), None
        ),
        integrity_issues=integrity_issues,
        repairable=repairable,
    )


def repair_projection_events(
    session: Session, *, installation_id: uuid.UUID, now: datetime | None = None
) -> int:
    """Requeue only work whose expired lease proves no dispatcher still owns it."""

    timestamp = now or _now()
    result = session.exec(
        update(ProjectionDispatchEvent)
        .where(
            _EVENT_TABLE.c.installation_id == installation_id,
            _EVENT_TABLE.c.status == "IN_PROGRESS",
            _EVENT_TABLE.c.lease_expires_at <= timestamp,
        )
        .values(
            status="PENDING",
            lease_token=None,
            lease_expires_at=None,
            available_at=timestamp,
            last_error="dispatch lease expired",
            updated_at=timestamp,
        )
        .execution_options(synchronize_session=False)
    )
    session.commit()
    repaired = result.rowcount
    corrupt_acknowledgements = session.exec(
        select(ProjectionDispatchEvent).where(
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.status == "ACKNOWLEDGED",
        )
    ).all()
    for event in corrupt_acknowledgements:
        receipt = session.exec(
            select(NativeProjectionReceipt).where(
                NativeProjectionReceipt.installation_id == installation_id,
                NativeProjectionReceipt.event_id == event.id,
            )
        ).first()
        if receipt is None or receipt.payload_digest != _payload_digest(event.payload):
            if receipt is not None:
                session.delete(receipt)
            event.status = "PENDING"
            event.acknowledged_at = None
            event.available_at = timestamp
            event.last_error = "acknowledgement receipt integrity repair"
            event.updated_at = timestamp
            session.add(event)
            repaired += 1
    session.commit()
    return repaired


def replay_dead_letter_projection_event(
    session: Session,
    *,
    installation_id: uuid.UUID,
    event_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
    now: datetime | None = None,
) -> bool:
    """Explicitly replay one dead-letter event after operator review."""

    timestamp = now or _now()
    event = session.exec(
        select(ProjectionDispatchEvent).where(
            ProjectionDispatchEvent.id == event_id,
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.status == "DEAD_LETTER",
        )
    ).first()
    if event is None:
        return False
    installation = session.get(ProductInstallation, installation_id)
    if installation is None or installation.tenant_id != event.tenant_id:
        return False
    result = session.exec(
        update(ProjectionDispatchEvent)
        .where(
            _EVENT_TABLE.c.id == event_id,
            _EVENT_TABLE.c.installation_id == installation_id,
            _EVENT_TABLE.c.status == "DEAD_LETTER",
        )
        .values(
            status="PENDING",
            attempt_count=0,
            available_at=timestamp,
            lease_token=None,
            lease_expires_at=None,
            dead_lettered_at=None,
            last_error=None,
            updated_at=timestamp,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 1:
        append_audit_event_to_session(
            session,
            event_name="revenueos.projection_dead_letter_replayed",
            workspace_id=str(event.tenant_id),
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type="projection_dispatch_event",
            resource_id=str(event.id),
            payload={"installation_id": str(installation_id), "event_type": event.event_type},
        )
    session.commit()
    return result.rowcount == 1
