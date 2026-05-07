"""Domain service: ``outbox service``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.domain_models import OutboxEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_outbox_event(
    session: Session,
    *,
    aggregate_id: uuid.UUID,
    aggregate_type: str,
    event_type: str,
    event_data: dict[str, Any],
    idempotency_key: str,
) -> OutboxEvent:
    """Enqueue outbox event."""
    existing = session.exec(
        select(OutboxEvent).where(OutboxEvent.idempotency_key == idempotency_key)
    ).first()
    if existing is not None:
        return existing

    event = OutboxEvent(
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        event_type=event_type,
        event_data=event_data,
        idempotency_key=idempotency_key,
        created_at=_now(),
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def list_unpublished_events(session: Session, *, limit: int = 100) -> list[OutboxEvent]:
    """Return a list of unpublished events."""
    return list(
        session.exec(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        ).all()
    )


def mark_outbox_published(session: Session, *, event_id: uuid.UUID) -> OutboxEvent | None:
    """Mark outbox published."""
    event = session.get(OutboxEvent, event_id)
    if event is None:
        return None

    event.published_at = _now()
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
