from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.contacts.progression_service import transition_contact_state
from app.domain_models import Campaign, Contact, ContactProgressionState, ContactStateHistory


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


# ---------------------------------------------------------------------------
# Story 5.1 — workspace_id tenant isolation
# ---------------------------------------------------------------------------

def _seed_contact_for_workspace(session: Session, workspace_id: str) -> uuid.UUID:
    contact = Contact(workspace_id=workspace_id, email=f"{workspace_id}@example.com")
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact.id


def _seed_campaign_for_workspace(session: Session, workspace_id: str) -> uuid.UUID:
    campaign = Campaign(
        workspace_id=workspace_id,
        name=f"Campaign for {workspace_id}",
        status="draft",
        created_by=uuid.uuid4(),
    )
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign.id


def test_state_history_workspace_id_populated_from_campaign(session: Session) -> None:
    """ContactStateHistory.workspace_id must be populated from the campaign."""
    workspace_id = "ws-hardening-a"
    contact_id = _seed_contact_for_workspace(session, workspace_id)
    campaign_id = _seed_campaign_for_workspace(session, workspace_id)

    transition_contact_state(
        session,
        contact_id=contact_id,
        campaign_id=campaign_id,
        to_state=ContactProgressionState.nurturing,
        reason="enrolled",
    )

    history = list(
        session.exec(
            select(ContactStateHistory).where(ContactStateHistory.contact_id == contact_id)
        ).all()
    )
    assert len(history) == 1
    assert history[0].workspace_id == workspace_id


def test_state_history_workspace_id_fallback_when_campaign_missing(session: Session) -> None:
    """When no matching campaign exists, workspace_id falls back to the contact's workspace_id."""
    ws = "ws-hardening-b"
    contact_id = _seed_contact_for_workspace(session, ws)
    missing_campaign_id = uuid.uuid4()  # not persisted

    transition_contact_state(
        session,
        contact_id=contact_id,
        campaign_id=missing_campaign_id,
        to_state=ContactProgressionState.nurturing,
        reason="fallback",
    )

    history = list(
        session.exec(
            select(ContactStateHistory).where(ContactStateHistory.contact_id == contact_id)
        ).all()
    )
    assert len(history) == 1
    assert history[0].workspace_id == ws


def test_state_history_cross_tenant_isolation(session: Session) -> None:
    """History rows from workspace A must not be visible via workspace B's column filter."""
    ws_a = "ws-tenant-a"
    ws_b = "ws-tenant-b"

    contact_a = _seed_contact_for_workspace(session, ws_a)
    contact_b = _seed_contact_for_workspace(session, ws_b)
    campaign_a = _seed_campaign_for_workspace(session, ws_a)
    campaign_b = _seed_campaign_for_workspace(session, ws_b)

    transition_contact_state(
        session, contact_id=contact_a, campaign_id=campaign_a,
        to_state=ContactProgressionState.nurturing, reason="ws-a enrolled",
    )
    transition_contact_state(
        session, contact_id=contact_b, campaign_id=campaign_b,
        to_state=ContactProgressionState.nurturing, reason="ws-b enrolled",
    )

    rows_a = list(
        session.exec(
            select(ContactStateHistory).where(
                ContactStateHistory.workspace_id == ws_a,
            )
        ).all()
    )
    rows_b = list(
        session.exec(
            select(ContactStateHistory).where(
                ContactStateHistory.workspace_id == ws_b,
            )
        ).all()
    )

    assert all(r.workspace_id == ws_a for r in rows_a), "Workspace A rows leaked into workspace B view"
    assert all(r.workspace_id == ws_b for r in rows_b), "Workspace B rows leaked into workspace A view"
    assert {r.contact_id for r in rows_a} == {contact_a}
    assert {r.contact_id for r in rows_b} == {contact_b}

