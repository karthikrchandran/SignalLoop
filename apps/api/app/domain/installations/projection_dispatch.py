"""Durable dispatch and reconciliation for native product projections."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.tenants.models import NativeProjectionReceipt, ProjectionDispatchEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_digest(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProjectionReconciliationStatus:
    pending: int
    acknowledged: int
    dead_letter: int
    last_error: str | None


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

    receipt = session.exec(
        select(NativeProjectionReceipt).where(
            NativeProjectionReceipt.installation_id == installation_id,
            NativeProjectionReceipt.event_id == event_id,
        )
    ).first()
    if receipt is None:
        receipt = NativeProjectionReceipt(
            installation_id=installation_id,
            event_id=event_id,
            payload_digest=payload_digest,
            acknowledged_at=now or _now(),
        )
        session.add(receipt)

    timestamp = now or _now()
    event.status = "ACKNOWLEDGED"
    event.acknowledged_at = timestamp
    event.last_error = None
    event.updated_at = timestamp
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(NativeProjectionReceipt).where(
                NativeProjectionReceipt.installation_id == installation_id,
                NativeProjectionReceipt.event_id == event_id,
            )
        ).first() is not None
    return True


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
    events = session.exec(
        select(ProjectionDispatchEvent)
        .where(
            ProjectionDispatchEvent.installation_id == installation_id,
            ProjectionDispatchEvent.status == "PENDING",
        )
        .order_by("created_at")
    ).all()
    dispatched = 0
    for event in events:
        try:
            apply(event)
        except Exception as error:
            event.attempt_count += 1
            event.last_error = str(error)[:500]
            event.updated_at = timestamp
            if event.attempt_count >= max_attempts:
                event.status = "DEAD_LETTER"
                event.dead_lettered_at = timestamp
            session.add(event)
            session.commit()
            continue

        if acknowledge_projection_event(
            session,
            installation_id=installation_id,
            event_id=event.id,
            payload_digest=_payload_digest(event.payload),
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
    return ProjectionReconciliationStatus(
        pending=sum(event.status == "PENDING" for event in events),
        acknowledged=sum(event.status == "ACKNOWLEDGED" for event in events),
        dead_letter=sum(event.status == "DEAD_LETTER" for event in events),
        last_error=next(
            (event.last_error for event in events if event.last_error is not None), None
        ),
    )
