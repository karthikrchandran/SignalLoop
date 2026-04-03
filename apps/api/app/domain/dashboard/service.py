"""Dashboard metrics service — aggregate queries for campaign visibility."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import func, case
from sqlmodel import Session, select

from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.voice.models import CallRequest, CallRequestStatus, CallSession, CallOutcome
from app.domain.signals.models import SignalEvent
from app.workers.call_worker import DAILY_CALL_CAP
from app.workers.sequence_worker import DEFAULT_DAILY_CAP as EMAIL_DAILY_CAP


def get_email_metrics(session: Session, campaign_id: uuid.UUID) -> dict:
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
            func.count(ContactSequenceState.id),
        )
        .where(ContactSequenceState.sequence_id.in_(seq_ids))
        .group_by(ContactSequenceState.status)
    ).all()

    state_map = {status: count for status, count in states}

    # Send request counts
    sends = session.exec(
        select(
            SendRequest.status,
            func.count(SendRequest.id),
        )
        .join(ContactSequenceState, SendRequest.contact_sequence_state_id == ContactSequenceState.id)
        .where(ContactSequenceState.sequence_id.in_(seq_ids))
        .group_by(SendRequest.status)
    ).all()

    send_map = {status: count for status, count in sends}

    return {
        "total_enrolled": sum(state_map.values()),
        "active": state_map.get(SequenceStatus.active, 0),
        "completed": state_map.get(SequenceStatus.completed, 0),
        "stopped": state_map.get(SequenceStatus.stopped, 0),
        "sent": send_map.get(SendRequestStatus.sent, 0),
        "failed": send_map.get(SendRequestStatus.failed, 0),
    }


def get_call_metrics(session: Session, campaign_id: uuid.UUID) -> dict:
    """Aggregate call metrics for a campaign."""
    # Call request counts
    call_statuses = session.exec(
        select(
            CallRequest.status,
            func.count(CallRequest.id),
        )
        .where(CallRequest.campaign_id == campaign_id)
        .group_by(CallRequest.status)
    ).all()

    status_map = {status: count for status, count in call_statuses}

    # Call outcome counts
    outcomes = session.exec(
        select(
            CallSession.outcome,
            func.count(CallSession.id),
        )
        .join(CallRequest, CallSession.call_request_id == CallRequest.id)
        .where(CallRequest.campaign_id == campaign_id)
        .group_by(CallSession.outcome)
    ).all()

    outcome_map = {outcome: count for outcome, count in outcomes}

    return {
        "total_queued": status_map.get(CallRequestStatus.queued, 0),
        "in_progress": status_map.get(CallRequestStatus.in_progress, 0),
        "completed": status_map.get(CallRequestStatus.completed, 0),
        "failed": status_map.get(CallRequestStatus.failed, 0),
        "answered": outcome_map.get(CallOutcome.answered, 0),
        "voicemail": outcome_map.get(CallOutcome.voicemail, 0),
        "no_answer": outcome_map.get(CallOutcome.no_answer, 0),
    }


def get_signal_summary(session: Session, campaign_id: uuid.UUID) -> dict:
    """Signal type breakdown for a campaign."""
    results = session.exec(
        select(
            SignalEvent.channel,
            SignalEvent.signal_type,
            func.count(SignalEvent.id),
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


def get_daily_cap_status(session: Session) -> dict:
    """Current daily send/call counts vs caps."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    email_count = session.exec(
        select(func.count(SendRequest.id)).where(
            SendRequest.status == SendRequestStatus.sent,
            SendRequest.created_at >= today_start,
        )
    ).one()

    call_count = session.exec(
        select(func.count(CallRequest.id)).where(
            CallRequest.status.in_([CallRequestStatus.in_progress, CallRequestStatus.completed]),
            CallRequest.created_at >= today_start,
        )
    ).one()

    return {
        "email_sent_today": email_count,
        "email_daily_cap": EMAIL_DAILY_CAP,
        "call_initiated_today": call_count,
        "call_daily_cap": DAILY_CALL_CAP,
    }
