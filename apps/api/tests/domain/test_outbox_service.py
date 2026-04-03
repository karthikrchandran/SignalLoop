from __future__ import annotations

import uuid

from sqlmodel import Session, SQLModel, create_engine

from app.domain.outreach.outbox_service import (
    enqueue_outbox_event,
    list_unpublished_events,
    mark_outbox_published,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_enqueue_outbox_event_is_idempotent() -> None:
    with _session() as session:
        aggregate_id = uuid.uuid4()
        first = enqueue_outbox_event(
            session,
            aggregate_id=aggregate_id,
            aggregate_type="contact",
            event_type="contact.progressed",
            event_data={"to_state": "nurturing"},
            idempotency_key="idem-1",
        )
        second = enqueue_outbox_event(
            session,
            aggregate_id=aggregate_id,
            aggregate_type="contact",
            event_type="contact.progressed",
            event_data={"to_state": "nurturing"},
            idempotency_key="idem-1",
        )

        assert first.id == second.id
        unpublished = list_unpublished_events(session)
        assert len(unpublished) == 1


def test_mark_outbox_published_sets_timestamp() -> None:
    with _session() as session:
        event = enqueue_outbox_event(
            session,
            aggregate_id=uuid.uuid4(),
            aggregate_type="contact",
            event_type="contact.progressed",
            event_data={"to_state": "replied"},
            idempotency_key="idem-2",
        )
        published = mark_outbox_published(session, event_id=event.id)

        assert published is not None
        assert published.published_at is not None
