from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.domain_models import ContactProgression, ContactProgressionState, ContactStateHistory

_ALLOWED_TRANSITIONS: dict[ContactProgressionState, set[ContactProgressionState]] = {
    ContactProgressionState.inbox: {ContactProgressionState.nurturing, ContactProgressionState.opted_out},
    ContactProgressionState.nurturing: {
        ContactProgressionState.engaged,
        ContactProgressionState.replied,
        ContactProgressionState.opted_out,
    },
    ContactProgressionState.engaged: {
        ContactProgressionState.replied,
        ContactProgressionState.booked,
        ContactProgressionState.opted_out,
    },
    ContactProgressionState.replied: {
        ContactProgressionState.booked,
        ContactProgressionState.handed_off,
        ContactProgressionState.opted_out,
    },
    ContactProgressionState.booked: {ContactProgressionState.handed_off},
    ContactProgressionState.handed_off: set(),
    ContactProgressionState.opted_out: set(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_progression(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> ContactProgression | None:
    return session.exec(
        select(ContactProgression).where(
            ContactProgression.contact_id == contact_id,
            ContactProgression.campaign_id == campaign_id,
        )
    ).first()


def transition_contact_state(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    to_state: ContactProgressionState,
    reason: str,
) -> ContactProgression:
    current = get_progression(session, contact_id=contact_id, campaign_id=campaign_id)
    now = _now()

    if current is None:
        progression = ContactProgression(
            contact_id=contact_id,
            campaign_id=campaign_id,
            current_state=to_state,
            last_action_at=now,
            updated_at=now,
        )
        session.add(progression)
        session.add(
            ContactStateHistory(
                contact_id=contact_id,
                campaign_id=campaign_id,
                from_state=ContactProgressionState.inbox,
                to_state=to_state,
                reason=reason,
                triggered_at=now,
            )
        )
        session.commit()
        session.refresh(progression)
        return progression

    from_state = current.current_state
    if to_state not in _ALLOWED_TRANSITIONS.get(from_state, set()):
        raise ValueError(f"Invalid transition from {from_state} to {to_state}")

    current.current_state = to_state
    current.last_action_at = now
    current.updated_at = now
    session.add(current)
    session.add(
        ContactStateHistory(
            contact_id=contact_id,
            campaign_id=campaign_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            triggered_at=now,
        )
    )
    session.commit()
    session.refresh(current)
    return current
