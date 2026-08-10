"""Domain service: ``action queue service``."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.domain_models import ActionQueue, DeadLetterEvent


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_action(
    session: Session,
    *,
    workspace_id: str,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    action_type: str,
    channel: str,
    payload: dict[str, Any],
) -> ActionQueue:
    """Enqueue action."""
    action = ActionQueue(
        workspace_id=workspace_id,
        contact_id=contact_id,
        campaign_id=campaign_id,
        action_type=action_type,
        channel=channel,
        payload=payload,
        status="pending",
        created_at=_now(),
    )
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def list_pending_actions(
    session: Session,
    *,
    workspace_id: str,
    limit: int = 100,
) -> list[ActionQueue]:
    """Return a list of pending actions."""
    return list(
        session.exec(
            select(ActionQueue)
            .where(
                ActionQueue.workspace_id == workspace_id,
                ActionQueue.status == "pending",
            )
            .order_by(ActionQueue.created_at)
            .limit(limit)
        ).all()
    )


def update_action_status(
    session: Session,
    *,
    workspace_id: str,
    action_id: uuid.UUID,
    status: str,
    next_retry_at: datetime | None = None,
) -> ActionQueue | None:
    """Update action status."""
    action = session.exec(
        select(ActionQueue).where(
            ActionQueue.workspace_id == workspace_id,
            ActionQueue.id == action_id,
        )
    ).first()
    if action is None:
        return None

    action.status = status
    action.next_retry_at = next_retry_at
    if status == "completed":
        action.executed_at = _now()
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


def write_dead_letter(
    session: Session,
    *,
    action: ActionQueue,
    failure_reason: str,
    workspace_id: str,
) -> ActionQueue:
    """Move an action queue item to dead-letter status and write a DeadLetterEvent row
    synchronously inside the same transaction (NFR8: visible within 60 s)."""
    if action.workspace_id != workspace_id:
        raise ValueError("Action queue workspace does not match dead-letter workspace")
    now = _now()
    action.status = "dead_letter"
    action.failure_reason = failure_reason
    action.dead_lettered_at = now
    session.add(action)

    dle = DeadLetterEvent(
        action_queue_id=action.id,
        campaign_id=action.campaign_id,
        contact_id=action.contact_id,
        workspace_id=workspace_id,
        action_type=action.action_type,
        failure_reason=failure_reason,
        event_type="dead_lettered",
        created_at=now,
    )
    session.add(dle)
    session.commit()
    session.refresh(action)
    return action
