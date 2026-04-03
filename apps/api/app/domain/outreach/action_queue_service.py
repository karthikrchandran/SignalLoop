from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.domain_models import ActionQueue


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_action(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    action_type: str,
    channel: str,
    payload: dict[str, Any],
) -> ActionQueue:
    action = ActionQueue(
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


def list_pending_actions(session: Session, *, limit: int = 100) -> list[ActionQueue]:
    return list(
        session.exec(
            select(ActionQueue)
            .where(ActionQueue.status == "pending")
            .order_by(ActionQueue.created_at)
            .limit(limit)
        ).all()
    )


def update_action_status(
    session: Session,
    *,
    action_id: uuid.UUID,
    status: str,
    next_retry_at: datetime | None = None,
) -> ActionQueue | None:
    action = session.get(ActionQueue, action_id)
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
