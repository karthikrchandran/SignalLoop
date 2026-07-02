"""Domain service: ``progression service``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.shared_records import service as shared_record_service
from app.domain.timeline.timeline_service import invalidate_timeline_cache_from_url_sync
from app.domain_models import (
    Campaign,
    ContactProgression,
    ContactProgressionState,
    ContactStateHistory,
)

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


def _invalidate_timeline(contact_id: uuid.UUID, campaign_id: uuid.UUID) -> None:
    invalidate_timeline_cache_from_url_sync(settings.REDIS_URL, contact_id, campaign_id)


def get_progression(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
) -> ContactProgression | None:
    """Return progression."""
    return session.exec(
        select(ContactProgression).where(
            ContactProgression.shared_contact_id == contact_id,
            ContactProgression.campaign_id == campaign_id,
        )
    ).first()


def _resolve_workspace_id(session: Session, *, contact_id: uuid.UUID, campaign_id: uuid.UUID) -> str:
    campaign = session.get(Campaign, campaign_id)
    if campaign:
        return campaign.workspace_id
    contact = shared_record_service.get_shared_contact(
        workspace_id=settings.DEFAULT_WORKSPACE_ID,
        contact_id=contact_id,
    )
    return contact.workspace_id if contact else "system"


def transition_contact_state(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    to_state: ContactProgressionState,
    reason: str,
) -> ContactProgression:
    """Transition contact state."""
    current = get_progression(session, contact_id=contact_id, campaign_id=campaign_id)
    now = _now()
    workspace_id = _resolve_workspace_id(session, contact_id=contact_id, campaign_id=campaign_id)

    if current is None:
        progression = ContactProgression(
            shared_contact_id=contact_id,
            campaign_id=campaign_id,
            current_state=to_state,
            last_action_at=now,
            updated_at=now,
        )
        session.add(progression)
        session.add(
            ContactStateHistory(
                workspace_id=workspace_id,
                shared_contact_id=contact_id,
                campaign_id=campaign_id,
                from_state=ContactProgressionState.inbox,
                to_state=to_state,
                reason=reason,
                triggered_at=now,
            )
        )
        append_audit_event_to_session(
            session,
            event_name="contact_state_transitioned",
            workspace_id=workspace_id,
            actor_role="system",
            resource_type="contact",
            resource_id=str(contact_id),
            payload={
                "contact_id": str(contact_id),
                "campaign_id": str(campaign_id),
                "from_state": ContactProgressionState.inbox.value,
                "to_state": to_state.value,
                "reason": reason,
            },
        )
        session.commit()
        _invalidate_timeline(contact_id, campaign_id)
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
            workspace_id=workspace_id,
            shared_contact_id=contact_id,
            campaign_id=campaign_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            triggered_at=now,
        )
    )
    append_audit_event_to_session(
        session,
        event_name="contact_state_transitioned",
        workspace_id=workspace_id,
        actor_role="system",
        resource_type="contact",
        resource_id=str(contact_id),
        payload={
            "contact_id": str(contact_id),
            "campaign_id": str(campaign_id),
            "from_state": from_state.value,
            "to_state": to_state.value,
            "reason": reason,
        },
    )
    session.commit()
    _invalidate_timeline(contact_id, campaign_id)
    session.refresh(current)
    return current
