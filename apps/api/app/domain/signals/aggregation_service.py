"""Signal aggregation service — cross-channel signal queries."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.signals.models import SignalEvent


def get_contact_signals(
    session: Session,
    shared_contact_id: uuid.UUID,
    *,
    workspace_id: str,
    channel: str | None = None,
    signal_type: str | None = None,
    since: datetime | None = None,
) -> list[SignalEvent]:
    """Return contact signals."""
    query = select(SignalEvent).where(
        SignalEvent.workspace_id == workspace_id,
        SignalEvent.shared_contact_id == shared_contact_id
    )
    if channel:
        query = query.where(SignalEvent.channel == channel)
    if signal_type:
        query = query.where(SignalEvent.signal_type == signal_type)
    if since:
        query = query.where(SignalEvent.created_at >= since)
    return list(session.exec(query.order_by(SignalEvent.created_at.desc())).all())


def get_latest_signal(
    session: Session, shared_contact_id: uuid.UUID, *, workspace_id: str
) -> SignalEvent | None:
    """Return latest signal."""
    return session.exec(
        select(SignalEvent)
        .where(
            SignalEvent.workspace_id == workspace_id,
            SignalEvent.shared_contact_id == shared_contact_id,
        )
        .order_by(SignalEvent.created_at.desc())
        .limit(1)
    ).first()


def get_campaign_signal_summary(
    session: Session, campaign_id: uuid.UUID, *, workspace_id: str
) -> dict[str, dict[str, int]]:
    """Returns signal counts grouped by channel and type."""
    results = session.exec(
        select(
            SignalEvent.channel,
            SignalEvent.signal_type,
            func.count(SignalEvent.id),
        )
        .where(
            SignalEvent.workspace_id == workspace_id,
            SignalEvent.campaign_id == campaign_id,
        )
        .group_by(SignalEvent.channel, SignalEvent.signal_type)
    ).all()

    summary: dict[str, dict[str, int]] = {}
    for channel, signal_type, count in results:
        if channel not in summary:
            summary[channel] = {}
        summary[channel][signal_type] = count
    return summary
