from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.schemas import (
    SequenceCreate,
    SequenceDetailPublic,
    SequencePublic,
    SequenceUpdate,
    StepPayload,
    StepPublic,
)
from app.domain_models import Contact, ContactProgression


def create_sequence(
    session: Session, *, data: SequenceCreate, created_by: uuid.UUID
) -> EmailSequence:
    seq = EmailSequence(
        campaign_id=data.campaign_id,
        name=data.name,
        created_by=created_by,
    )
    session.add(seq)
    session.commit()
    session.refresh(seq)
    return seq


def get_sequence_or_404(session: Session, sequence_id: uuid.UUID) -> EmailSequence:
    seq = session.get(EmailSequence, sequence_id)
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return seq


def get_sequence_detail(session: Session, sequence_id: uuid.UUID) -> SequenceDetailPublic:
    seq = get_sequence_or_404(session, sequence_id)
    steps = session.exec(
        select(SequenceStep)
        .where(SequenceStep.sequence_id == sequence_id)
        .order_by(SequenceStep.step_order)
    ).all()
    return SequenceDetailPublic(
        id=seq.id,
        campaign_id=seq.campaign_id,
        name=seq.name,
        active=seq.active,
        created_at=seq.created_at,
        steps=[
            StepPublic(
                id=s.id,
                step_order=s.step_order,
                delay_days=s.delay_days,
                subject_template=s.subject_template,
                body_template=s.body_template,
            )
            for s in steps
        ],
    )


def update_sequence(
    session: Session, *, sequence_id: uuid.UUID, data: SequenceUpdate
) -> EmailSequence:
    seq = get_sequence_or_404(session, sequence_id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(seq, key, value)
    seq.updated_at = datetime.now(timezone.utc)
    session.add(seq)
    session.commit()
    session.refresh(seq)
    return seq


def batch_upsert_steps(
    session: Session, *, sequence_id: uuid.UUID, steps: list[StepPayload]
) -> list[SequenceStep]:
    get_sequence_or_404(session, sequence_id)
    # Delete existing steps and recreate (simple upsert strategy)
    existing = session.exec(
        select(SequenceStep).where(SequenceStep.sequence_id == sequence_id)
    ).all()
    for step in existing:
        session.delete(step)
    session.flush()

    new_steps: list[SequenceStep] = []
    for payload in sorted(steps, key=lambda s: s.step_order):
        step = SequenceStep(
            sequence_id=sequence_id,
            step_order=payload.step_order,
            delay_days=payload.delay_days,
            subject_template=payload.subject_template,
            body_template=payload.body_template,
        )
        session.add(step)
        new_steps.append(step)
    session.commit()
    for step in new_steps:
        session.refresh(step)
    return new_steps


def delete_sequence(session: Session, sequence_id: uuid.UUID) -> None:
    seq = get_sequence_or_404(session, sequence_id)
    # Delete steps first
    steps = session.exec(
        select(SequenceStep).where(SequenceStep.sequence_id == sequence_id)
    ).all()
    for step in steps:
        session.delete(step)
    # Delete contact sequence states
    states = session.exec(
        select(ContactSequenceState).where(
            ContactSequenceState.sequence_id == sequence_id
        )
    ).all()
    for state in states:
        session.delete(state)
    session.delete(seq)
    session.commit()


def enroll_campaign_contacts(
    session: Session, *, campaign_id: uuid.UUID, sequence_id: uuid.UUID
) -> int:
    """Enroll all campaign contacts into a sequence with next_send_at = now."""
    get_sequence_or_404(session, sequence_id)
    # Get all contact IDs linked to this campaign via contact_progression
    progressions = session.exec(
        select(ContactProgression.contact_id).where(
            ContactProgression.campaign_id == campaign_id
        )
    ).all()

    now = datetime.now(timezone.utc)
    enrolled = 0
    for contact_id in progressions:
        # Check if already enrolled
        existing = session.exec(
            select(ContactSequenceState).where(
                ContactSequenceState.contact_id == contact_id,
                ContactSequenceState.sequence_id == sequence_id,
            )
        ).first()
        if existing:
            continue
        state = ContactSequenceState(
            contact_id=contact_id,
            sequence_id=sequence_id,
            current_step=1,
            next_send_at=now,
            status=SequenceStatus.active,
        )
        session.add(state)
        enrolled += 1
    session.commit()
    return enrolled
