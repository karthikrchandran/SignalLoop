from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.contacts.progression_service import transition_contact_state
from app.domain_models import Contact, ContactProgressionState, ContactStateHistory


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _seed_contact(session: Session) -> uuid.UUID:
    contact = Contact(workspace_id="ws-epic2", email="test@example.com")
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact.id


def test_transition_creates_progression_and_history(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = uuid.uuid4()

    progression = transition_contact_state(
        session,
        contact_id=contact_id,
        campaign_id=campaign_id,
        to_state=ContactProgressionState.nurturing,
        reason="initial import",
    )

    assert progression.current_state == ContactProgressionState.nurturing

    history = list(
        session.exec(
            select(ContactStateHistory).where(ContactStateHistory.contact_id == contact_id)
        ).all()
    )
    assert len(history) == 1
    assert history[0].to_state == ContactProgressionState.nurturing


def test_invalid_transition_raises(session: Session) -> None:
    contact_id = _seed_contact(session)
    campaign_id = uuid.uuid4()

    transition_contact_state(
        session,
        contact_id=contact_id,
        campaign_id=campaign_id,
        to_state=ContactProgressionState.nurturing,
        reason="initial import",
    )

    with pytest.raises(ValueError):
        transition_contact_state(
            session,
            contact_id=contact_id,
            campaign_id=campaign_id,
            to_state=ContactProgressionState.booked,
            reason="skip stages",
        )
