"""Dashboard metrics service — aggregate queries for campaign visibility."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.signals.models import SignalEvent
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
)
from app.domain_models import Campaign
from app.workers.call_worker import DAILY_CALL_CAP
from app.workers.sequence_worker import DEFAULT_DAILY_CAP as EMAIL_DAILY_CAP


def get_email_metrics(session: Session, campaign_id: uuid.UUID) -> dict[str, Any]:
    """Aggregate email metrics for a campaign."""
    sequences = session.exec(
        select(EmailSequence.id).where(EmailSequence.campaign_id == campaign_id)
    ).all()

    if not sequences:
        return {"total_enrolled": 0, "active": 0, "completed": 0, "stopped": 0, "sent": 0, "failed": 0}

    seq_ids = list(sequences)

    # Contact state counts
    states = session.exec(
        select(
            ContactSequenceState.status,
            func.count(col(ContactSequenceState.id)),
        )
        .where(col(ContactSequenceState.sequence_id).in_(seq_ids))
        .group_by(ContactSequenceState.status)
    ).all()

    state_map = dict(states)

    # Send request counts
    sends = session.exec(
        select(
            SendRequest.status,
            func.count(col(SendRequest.id)),
        )
        .join(ContactSequenceState, col(SendRequest.contact_sequence_state_id) == col(ContactSequenceState.id))
        .where(col(ContactSequenceState.sequence_id).in_(seq_ids))
        .group_by(SendRequest.status)
    ).all()

    send_map = dict(sends)

    return {
        "total_enrolled": sum(state_map.values()),
        "active": state_map.get(SequenceStatus.active, 0),
        "completed": state_map.get(SequenceStatus.completed, 0),
        "stopped": state_map.get(SequenceStatus.stopped, 0),
        "sent": send_map.get(SendRequestStatus.sent, 0),
        "failed": send_map.get(SendRequestStatus.failed, 0),
    }


def get_call_metrics(session: Session, campaign_id: uuid.UUID) -> dict[str, Any]:
    """Aggregate call metrics for a campaign."""
    # Call request counts
    call_statuses = session.exec(
        select(
            CallRequest.status,
            func.count(col(CallRequest.id)),
        )
        .where(CallRequest.campaign_id == campaign_id)
        .group_by(CallRequest.status)
    ).all()

    status_map = dict(call_statuses)

    # Call outcome counts
    outcomes = session.exec(
        select(
            CallSession.outcome,
            func.count(col(CallSession.id)),
        )
        .join(CallRequest, col(CallSession.call_request_id) == col(CallRequest.id))
        .where(CallRequest.campaign_id == campaign_id)
        .group_by(CallSession.outcome)
    ).all()

    outcome_map = dict(outcomes)

    return {
        "total_queued": status_map.get(CallRequestStatus.queued, 0),
        "in_progress": status_map.get(CallRequestStatus.in_progress, 0),
        "completed": status_map.get(CallRequestStatus.completed, 0),
        "failed": status_map.get(CallRequestStatus.failed, 0),
        "answered": outcome_map.get(CallOutcome.answered, 0),
        "voicemail": outcome_map.get(CallOutcome.voicemail, 0),
        "no_answer": outcome_map.get(CallOutcome.no_answer, 0),
    }


def get_signal_summary(session: Session, campaign_id: uuid.UUID) -> dict[str, Any]:
    """Signal type breakdown for a campaign."""
    results = session.exec(
        select(
            SignalEvent.channel,
            SignalEvent.signal_type,
            func.count(col(SignalEvent.id)),
        )
        .where(SignalEvent.campaign_id == campaign_id)
        .group_by(SignalEvent.channel, SignalEvent.signal_type)
    ).all()

    summary: dict[str, dict[str, int]] = {}
    for channel, signal_type, count in results:
        if channel not in summary:
            summary[channel] = {}
        summary[channel][signal_type] = count
    return summary


def get_daily_cap_status(session: Session, *, workspace_id: str) -> dict[str, Any]:
    """Current daily send/call counts vs caps."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    email_count = session.exec(
        select(func.count(col(SendRequest.id)))
        .join(ContactSequenceState, col(SendRequest.contact_sequence_state_id) == col(ContactSequenceState.id))
        .join(EmailSequence, col(ContactSequenceState.sequence_id) == col(EmailSequence.id))
        .join(Campaign, col(EmailSequence.campaign_id) == col(Campaign.id))
        .where(
            col(SendRequest.status) == SendRequestStatus.sent,
            col(SendRequest.created_at) >= today_start,
            col(Campaign.workspace_id) == workspace_id,
        )
    ).one()

    call_count = session.exec(
        select(func.count(col(CallRequest.id)))
        .join(Campaign, col(CallRequest.campaign_id) == col(Campaign.id))
        .where(
            col(CallRequest.status).in_([CallRequestStatus.in_progress, CallRequestStatus.completed]),
            col(CallRequest.created_at) >= today_start,
            col(Campaign.workspace_id) == workspace_id,
        )
    ).one()

    return {
        "email_sent_today": email_count,
        "email_daily_cap": EMAIL_DAILY_CAP,
        "call_initiated_today": call_count,
        "call_daily_cap": DAILY_CALL_CAP,
    }
