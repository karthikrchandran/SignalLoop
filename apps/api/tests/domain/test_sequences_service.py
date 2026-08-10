"""Unit tests for ``app.domain.sequences.service`` covering all branches."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.schemas import (
    SequenceCreate,
    SequenceUpdate,
    StepPayload,
)
from app.domain.sequences.service import (
    batch_upsert_steps,
    create_sequence,
    delete_sequence,
    enroll_campaign_contacts,
    get_sequence_detail,
    get_sequence_or_404,
    update_sequence,
)
from app.domain_models import (
    Campaign,
    Contact,
    ContactProgression,
    ContactProgressionState,
)


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def _seed_contact(session: Session, email: str = "c@example.com") -> uuid.UUID:
    contact = Contact(workspace_id="ws", email=email)
    session.add(contact)
    session.commit()
    session.refresh(contact)
    return contact.id


def _seed_campaign(session: Session) -> uuid.UUID:
    campaign = Campaign(name="Sequence campaign", workspace_id="ws", created_by=uuid.uuid4())
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return campaign.id


def _seed_progression(
    session: Session, contact_id: uuid.UUID, campaign_id: uuid.UUID
) -> None:
    session.add(
        ContactProgression(
            contact_id=contact_id,
            campaign_id=campaign_id,
            current_state=ContactProgressionState.nurturing,
        )
    )
    session.commit()


def test_create_sequence_persists_record(session: Session) -> None:
    """create_sequence inserts row and returns refreshed model."""
    data = SequenceCreate(name="Welcome", campaign_id=_seed_campaign(session))
    seq = create_sequence(session, data=data, created_by=uuid.uuid4())
    assert seq.id is not None
    assert seq.name == "Welcome"
    assert seq.active is True


def test_get_sequence_or_404_returns_existing(session: Session) -> None:
    """get_sequence_or_404 returns model when present."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    found = get_sequence_or_404(session, seq.id)
    assert found.id == seq.id


def test_get_sequence_or_404_raises_when_missing(session: Session) -> None:
    """get_sequence_or_404 raises 404 when no row exists."""
    with pytest.raises(HTTPException) as exc:
        get_sequence_or_404(session, uuid.uuid4())
    assert exc.value.status_code == 404


def test_get_sequence_detail_includes_steps_in_order(session: Session) -> None:
    """get_sequence_detail returns steps sorted by step_order."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    session.add(SequenceStep(sequence_id=seq.id, step_order=2, subject_template="s2", body_template="b2"))
    session.add(SequenceStep(sequence_id=seq.id, step_order=1, subject_template="s1", body_template="b1"))
    session.commit()

    detail = get_sequence_detail(session, seq.id)
    assert detail.id == seq.id
    assert [s.step_order for s in detail.steps] == [1, 2]


def test_get_sequence_detail_empty_steps(session: Session) -> None:
    """get_sequence_detail returns empty list when no steps exist."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    detail = get_sequence_detail(session, seq.id)
    assert detail.steps == []


def test_update_sequence_modifies_only_provided_fields(session: Session) -> None:
    """update_sequence applies partial update via exclude_unset."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="Old", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    updated = update_sequence(
        session, sequence_id=seq.id, data=SequenceUpdate(name="New")
    )
    assert updated.name == "New"
    assert updated.active is True


def test_update_sequence_can_deactivate(session: Session) -> None:
    """update_sequence can flip active flag."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="N", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    updated = update_sequence(
        session, sequence_id=seq.id, data=SequenceUpdate(active=False)
    )
    assert updated.active is False


def test_update_sequence_missing_raises_404(session: Session) -> None:
    """update_sequence on unknown id raises 404."""
    with pytest.raises(HTTPException):
        update_sequence(
            session, sequence_id=uuid.uuid4(), data=SequenceUpdate(name="x")
        )


def test_batch_upsert_steps_replaces_existing(session: Session) -> None:
    """batch_upsert_steps deletes existing and creates new sorted set."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    # Pre-populate with stale step
    session.add(SequenceStep(sequence_id=seq.id, step_order=99, subject_template="old", body_template="old"))
    session.commit()

    payload = [
        StepPayload(step_order=2, subject_template="s2", body_template="b2"),
        StepPayload(step_order=1, subject_template="s1", body_template="b1", delay_days=3),
    ]
    new_steps = batch_upsert_steps(session, sequence_id=seq.id, steps=payload)

    assert [s.step_order for s in new_steps] == [1, 2]
    assert new_steps[0].delay_days == 3
    remaining = session.exec(
        select(SequenceStep).where(SequenceStep.sequence_id == seq.id)
    ).all()
    assert len(remaining) == 2


def test_batch_upsert_steps_empty_payload_clears_steps(session: Session) -> None:
    """Passing empty list deletes existing without creating new ones."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    session.add(SequenceStep(sequence_id=seq.id, step_order=1, subject_template="s", body_template="b"))
    session.commit()

    result = batch_upsert_steps(session, sequence_id=seq.id, steps=[])
    assert result == []
    remaining = session.exec(
        select(SequenceStep).where(SequenceStep.sequence_id == seq.id)
    ).all()
    assert remaining == []


def test_batch_upsert_steps_missing_sequence_raises(session: Session) -> None:
    """Unknown sequence_id raises 404 before mutating anything."""
    with pytest.raises(HTTPException):
        batch_upsert_steps(session, sequence_id=uuid.uuid4(), steps=[])


def test_delete_sequence_cascades_steps_and_states(session: Session) -> None:
    """delete_sequence removes sequence, steps, and contact states."""
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=_seed_campaign(session)),
        created_by=uuid.uuid4(),
    )
    contact_id = _seed_contact(session)
    session.add(SequenceStep(sequence_id=seq.id, step_order=1, subject_template="s", body_template="b"))
    session.add(
        ContactSequenceState(contact_id=contact_id, sequence_id=seq.id, current_step=1)
    )
    session.commit()

    delete_sequence(session, seq.id)

    assert session.get(EmailSequence, seq.id) is None
    assert session.exec(select(SequenceStep).where(SequenceStep.sequence_id == seq.id)).all() == []
    assert (
        session.exec(
            select(ContactSequenceState).where(ContactSequenceState.sequence_id == seq.id)
        ).all()
        == []
    )


def test_delete_sequence_missing_raises(session: Session) -> None:
    """delete_sequence on unknown id raises 404."""
    with pytest.raises(HTTPException):
        delete_sequence(session, uuid.uuid4())


def test_enroll_campaign_contacts_creates_states(session: Session) -> None:
    """enroll_campaign_contacts adds a state per progression contact."""
    campaign_id = _seed_campaign(session)
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=campaign_id),
        created_by=uuid.uuid4(),
    )
    c1 = _seed_contact(session, "a@example.com")
    c2 = _seed_contact(session, "b@example.com")
    _seed_progression(session, c1, campaign_id)
    _seed_progression(session, c2, campaign_id)

    enrolled = enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=seq.id
    )
    assert enrolled == 2
    states = session.exec(
        select(ContactSequenceState).where(ContactSequenceState.sequence_id == seq.id)
    ).all()
    assert len(states) == 2
    assert all(s.status == SequenceStatus.active for s in states)
    assert all(s.current_step == 1 for s in states)


def test_enroll_campaign_contacts_skips_already_enrolled(session: Session) -> None:
    """Re-enrolling does not duplicate existing states."""
    campaign_id = _seed_campaign(session)
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=campaign_id),
        created_by=uuid.uuid4(),
    )
    c1 = _seed_contact(session)
    _seed_progression(session, c1, campaign_id)

    first = enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=seq.id
    )
    second = enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=seq.id
    )
    assert first == 1
    assert second == 0


def test_enroll_campaign_contacts_no_progressions(session: Session) -> None:
    """Returns 0 when no contacts exist for the campaign."""
    campaign_id = _seed_campaign(session)
    seq = create_sequence(
        session,
        data=SequenceCreate(name="X", campaign_id=campaign_id),
        created_by=uuid.uuid4(),
    )
    enrolled = enroll_campaign_contacts(
        session, campaign_id=campaign_id, sequence_id=seq.id
    )
    assert enrolled == 0


def test_enroll_campaign_contacts_missing_sequence_raises(session: Session) -> None:
    """Unknown sequence raises 404 before any insert."""
    with pytest.raises(HTTPException):
        enroll_campaign_contacts(
            session, campaign_id=uuid.uuid4(), sequence_id=uuid.uuid4()
        )
