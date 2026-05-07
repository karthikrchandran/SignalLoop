"""Timeline aggregation service for contact explainability (Story 5.1)."""
from __future__ import annotations

import asyncio
import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.domain.signals.models import SignalEvent
from app.domain.signals.scheduling import SchedulingRequest
from app.domain.voice.models import CallRequest, CallSession
from app.domain_models import (
    Campaign,
    ContactEvent,
    ContactStateHistory,
    RoutingDecision,
    TimelineEventDetailPublic,
    TimelineEventPublic,
    TimelinePagePublic,
)

# Source-system prefix -> table identifier
_CSH = "csh"
_CE = "ce"
_RD = "rd"
_SIG = "sig"
_SCHED = "sched"
_CALL = "call"

TIMELINE_CACHE_TTL = 30  # seconds
REDIS_CACHE_TIMEOUT = 0.25  # seconds


def _metadata_value(metadata: dict[str, Any] | None, *keys: str) -> str | None:
    if not metadata:
        return None
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _reason_code_explanation(
    reason_code: str | None,
    metadata: dict[str, Any] | None = None,
    fallback: str | None = None,
) -> str | None:
    explicit = _metadata_value(
        metadata,
        "reason_code_explanation",
        "reasonExplanation",
        "explanation",
        "reason_text",
    )
    if explicit:
        return explicit
    if fallback:
        return fallback
    if reason_code:
        return reason_code.replace("_", " ").capitalize()
    return None


def _confidence_tier(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _transcript_excerpt(transcript: str | None, limit: int = 500) -> str | None:
    if not transcript:
        return None
    normalized = " ".join(transcript.split())
    if not normalized:
        return None
    return normalized[:limit] + ("..." if len(normalized) > limit else "")


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _event_sort_key(event: TimelineEventPublic) -> tuple[datetime, str]:
    return (_to_utc(event.timestamp), event.id)


def _encode_cursor(event: TimelineEventPublic) -> str:
    raw = f"{_to_utc(event.timestamp).isoformat()}|{event.id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        timestamp_raw, event_id = raw.split("|", 1)
        return (_to_utc(datetime.fromisoformat(timestamp_raw)), event_id)
    except Exception:  # noqa: BLE001
        return None


def _event_type_values(event_type_filter: str | None) -> set[str] | None:
    if not event_type_filter:
        return None
    values = {
        value.strip()
        for value in event_type_filter.split(",")
        if value.strip() and value.strip() != "all"
    }
    return values or None


def _event_type_in(values: set[str] | None, *names: str) -> bool:
    return values is None or bool(values.intersection(names))


def _parse_prefixed_id(prefixed_id: str) -> tuple[str, uuid.UUID]:
    """Parse 'csh_<hex>' -> ('csh', UUID). Raises ValueError on bad format."""
    parts = prefixed_id.split("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid event id format: {prefixed_id!r}")
    prefix, hex_str = parts
    return prefix, uuid.UUID(hex_str)


def _csh_to_event(row: ContactStateHistory) -> TimelineEventPublic:
    return TimelineEventPublic(
        id=f"{_CSH}_{row.id.hex}",
        source_system="contact_state_history",
        event_type="state_transition",
        channel=None,
        timestamp=row.triggered_at,
        actor="system",
        outcome=row.to_state.value,
        reason_code=row.reason,
        has_detail=bool(row.reason),
    )


def _ce_to_event(row: ContactEvent) -> TimelineEventPublic:
    return TimelineEventPublic(
        id=f"{_CE}_{row.id.hex}",
        source_system="contact_events",
        event_type=row.event_type,
        channel=row.channel,
        timestamp=row.created_at,
        actor=row.actor,
        outcome=row.outcome,
        reason_code=row.reason_code,
        rule_ref=row.rule_ref,
        template_ref=row.template_ref,
        confidence_tier=row.confidence_tier,
        has_detail=bool(
            row.reason_code
            or row.rule_ref
            or row.template_ref
            or row.confidence_tier
            or row.event_metadata
        ),
    )


def _rd_to_event(row: RoutingDecision) -> TimelineEventPublic:
    return TimelineEventPublic(
        id=f"{_RD}_{row.id.hex}",
        source_system="routing_decisions",
        event_type=row.decision_type,
        channel=None,
        timestamp=row.created_at,
        actor="system",
        outcome=row.outcome,
        reason_code=row.reason_code,
        rule_ref=row.rule_name,
        confidence_tier=row.confidence_tier,
        has_detail=bool(row.reason_code or row.rule_condition or row.signal_summary),
    )


def _signal_to_event(row: SignalEvent) -> TimelineEventPublic:
    return TimelineEventPublic(
        id=f"{_SIG}_{row.id.hex}",
        source_system="signal_events",
        event_type=row.signal_type,
        channel=row.channel,
        timestamp=row.created_at,
        actor="system",
        outcome="detected",
        reason_code=row.signal_type,
        confidence_tier=_confidence_tier(row.confidence),
        has_detail=True,
    )


def _scheduling_to_event(row: SchedulingRequest) -> TimelineEventPublic:
    status = row.status.value if hasattr(row.status, "value") else str(row.status)
    return TimelineEventPublic(
        id=f"{_SCHED}_{row.id.hex}",
        source_system="scheduling_requests",
        event_type="booking_event" if status == "booked" else "scheduling_request",
        channel="scheduling",
        timestamp=row.created_at,
        actor="system",
        outcome=status,
        reason_code="scheduling_requested",
        has_detail=True,
    )


def _call_to_event(session_row: CallSession, request_row: CallRequest) -> TimelineEventPublic:
    outcome = session_row.outcome.value if session_row.outcome else session_row.twilio_status
    return TimelineEventPublic(
        id=f"{_CALL}_{session_row.id.hex}",
        source_system="call_sessions",
        event_type="call_session",
        channel="voice",
        timestamp=session_row.twilio_status_updated_at or session_row.created_at,
        actor="system",
        outcome=outcome,
        reason_code=request_row.trigger_reason,
        has_detail=bool(
            session_row.transcript
            or session_row.recording_url
            or session_row.unanswered_questions
            or request_row.trigger_reason
        ),
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_key(contact_id: uuid.UUID, campaign_id: uuid.UUID | None) -> str:
    campaign_part = campaign_id.hex if campaign_id else "all"
    return f"timeline:{contact_id.hex}:{campaign_part}:page1"


def timeline_cache_keys(
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> tuple[str, ...]:
    keys = [_cache_key(contact_id, None)]
    if campaign_id:
        keys.append(_cache_key(contact_id, campaign_id))
    return tuple(keys)


async def _get_cached(request: Request, key: str) -> dict[str, Any] | None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return None
        raw = await asyncio.wait_for(redis.get(key), timeout=REDIS_CACHE_TIMEOUT)
        if not raw:
            return None
        loaded = json.loads(raw)
        if isinstance(loaded, list):
            return {"data": loaded, "count": len(loaded)}
        return loaded if isinstance(loaded, dict) else None
    except Exception:  # noqa: BLE001
        return None


async def _set_cached(request: Request, key: str, data: dict[str, Any]) -> None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return
        await asyncio.wait_for(
            redis.setex(key, TIMELINE_CACHE_TTL, json.dumps(data, default=str)),
            timeout=REDIS_CACHE_TIMEOUT,
        )
    except Exception:  # noqa: BLE001
        pass


async def invalidate_timeline_cache(
    request: Request,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> None:
    """Invalidate first-page timeline caches for a contact after event writes."""
    try:
        redis = request.app.state.redis_manager.client
    except Exception:  # noqa: BLE001
        return
    await invalidate_timeline_cache_for_client(redis, contact_id, campaign_id)


async def invalidate_timeline_cache_for_client(
    redis: Any,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> None:
    if redis is None:
        return
    try:
        await asyncio.wait_for(
            redis.delete(*timeline_cache_keys(contact_id, campaign_id)),
            timeout=REDIS_CACHE_TIMEOUT,
        )
    except Exception:  # noqa: BLE001
        pass


async def invalidate_timeline_cache_from_url(
    redis_url: str,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> None:
    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        await invalidate_timeline_cache_for_client(redis, contact_id, campaign_id)
    finally:
        await redis.aclose()


def invalidate_timeline_cache_from_url_sync(
    redis_url: str,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(invalidate_timeline_cache_from_url(redis_url, contact_id, campaign_id))
        return
    loop.create_task(invalidate_timeline_cache_from_url(redis_url, contact_id, campaign_id))


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------


def _count(session: Session, stmt: Any) -> int:
    return int(session.exec(stmt).first() or 0)


def _fetch_state_history(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[ContactStateHistory], int]:
    if not _event_type_in(event_types, "state_transition"):
        return [], 0

    count_stmt = (
        select(func.count(ContactStateHistory.id))
        .select_from(ContactStateHistory)
        .join(Campaign, ContactStateHistory.campaign_id == Campaign.id)
        .where(
            ContactStateHistory.contact_id == contact_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    stmt = (
        select(ContactStateHistory)
        .join(Campaign, ContactStateHistory.campaign_id == Campaign.id)
        .where(
            ContactStateHistory.contact_id == contact_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    if campaign_id:
        count_stmt = count_stmt.where(ContactStateHistory.campaign_id == campaign_id)
        stmt = stmt.where(ContactStateHistory.campaign_id == campaign_id)
    if from_dt:
        count_stmt = count_stmt.where(ContactStateHistory.triggered_at >= from_dt)
        stmt = stmt.where(ContactStateHistory.triggered_at >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(ContactStateHistory.triggered_at <= to_dt)
        stmt = stmt.where(ContactStateHistory.triggered_at <= to_dt)
    if cursor_key:
        stmt = stmt.where(ContactStateHistory.triggered_at <= cursor_key[0])

    rows = session.exec(
        stmt.order_by(ContactStateHistory.triggered_at.desc()).limit(source_limit)
    ).all()
    return list(rows), _count(session, count_stmt)


def _fetch_contact_events(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[ContactEvent], int]:
    count_stmt = select(func.count(ContactEvent.id)).where(
        ContactEvent.contact_id == contact_id,
        ContactEvent.workspace_id == workspace_id,
    )
    stmt = select(ContactEvent).where(
        ContactEvent.contact_id == contact_id,
        ContactEvent.workspace_id == workspace_id,
    )
    if campaign_id:
        count_stmt = count_stmt.where(ContactEvent.campaign_id == campaign_id)
        stmt = stmt.where(ContactEvent.campaign_id == campaign_id)
    if event_types:
        count_stmt = count_stmt.where(ContactEvent.event_type.in_(event_types))
        stmt = stmt.where(ContactEvent.event_type.in_(event_types))
    if from_dt:
        count_stmt = count_stmt.where(ContactEvent.created_at >= from_dt)
        stmt = stmt.where(ContactEvent.created_at >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(ContactEvent.created_at <= to_dt)
        stmt = stmt.where(ContactEvent.created_at <= to_dt)
    if cursor_key:
        stmt = stmt.where(ContactEvent.created_at <= cursor_key[0])

    rows = session.exec(stmt.order_by(ContactEvent.created_at.desc()).limit(source_limit)).all()
    return list(rows), _count(session, count_stmt)


def _fetch_routing_decisions(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[RoutingDecision], int]:
    if event_types and not event_types.intersection({"routing", "routing_decision"}):
        return [], 0

    count_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.contact_id == contact_id,
        RoutingDecision.workspace_id == workspace_id,
    )
    stmt = select(RoutingDecision).where(
        RoutingDecision.contact_id == contact_id,
        RoutingDecision.workspace_id == workspace_id,
    )
    if campaign_id:
        count_stmt = count_stmt.where(RoutingDecision.campaign_id == campaign_id)
        stmt = stmt.where(RoutingDecision.campaign_id == campaign_id)
    if event_types:
        decision_types = event_types.intersection({"routing", "routing_decision"})
        count_stmt = count_stmt.where(RoutingDecision.decision_type.in_(decision_types))
        stmt = stmt.where(RoutingDecision.decision_type.in_(decision_types))
    if from_dt:
        count_stmt = count_stmt.where(RoutingDecision.created_at >= from_dt)
        stmt = stmt.where(RoutingDecision.created_at >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(RoutingDecision.created_at <= to_dt)
        stmt = stmt.where(RoutingDecision.created_at <= to_dt)
    if cursor_key:
        stmt = stmt.where(RoutingDecision.created_at <= cursor_key[0])

    rows = session.exec(stmt.order_by(RoutingDecision.created_at.desc()).limit(source_limit)).all()
    return list(rows), _count(session, count_stmt)


def _fetch_signal_events(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[SignalEvent], int]:
    count_stmt = (
        select(func.count(SignalEvent.id))
        .select_from(SignalEvent)
        .join(Campaign, SignalEvent.campaign_id == Campaign.id)
        .where(SignalEvent.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    stmt = (
        select(SignalEvent)
        .join(Campaign, SignalEvent.campaign_id == Campaign.id)
        .where(SignalEvent.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    if campaign_id:
        count_stmt = count_stmt.where(SignalEvent.campaign_id == campaign_id)
        stmt = stmt.where(SignalEvent.campaign_id == campaign_id)
    if event_types and not event_types.intersection({"signal", "signal_event"}):
        count_stmt = count_stmt.where(SignalEvent.signal_type.in_(event_types))
        stmt = stmt.where(SignalEvent.signal_type.in_(event_types))
    if from_dt:
        count_stmt = count_stmt.where(SignalEvent.created_at >= from_dt)
        stmt = stmt.where(SignalEvent.created_at >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(SignalEvent.created_at <= to_dt)
        stmt = stmt.where(SignalEvent.created_at <= to_dt)
    if cursor_key:
        stmt = stmt.where(SignalEvent.created_at <= cursor_key[0])

    rows = session.exec(stmt.order_by(SignalEvent.created_at.desc()).limit(source_limit)).all()
    return list(rows), _count(session, count_stmt)


def _fetch_scheduling_requests(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[SchedulingRequest], int]:
    status_values = {"pending", "contacted", "booked", "declined"}
    if event_types and not event_types.intersection(
        {"booking", "booking_event", "scheduling", "scheduling_request"} | status_values
    ):
        return [], 0

    count_stmt = (
        select(func.count(SchedulingRequest.id))
        .select_from(SchedulingRequest)
        .join(Campaign, SchedulingRequest.campaign_id == Campaign.id)
        .where(SchedulingRequest.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    stmt = (
        select(SchedulingRequest)
        .join(Campaign, SchedulingRequest.campaign_id == Campaign.id)
        .where(SchedulingRequest.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    if campaign_id:
        count_stmt = count_stmt.where(SchedulingRequest.campaign_id == campaign_id)
        stmt = stmt.where(SchedulingRequest.campaign_id == campaign_id)
    if event_types:
        selected_statuses = event_types.intersection(status_values)
        if selected_statuses:
            count_stmt = count_stmt.where(SchedulingRequest.status.in_(selected_statuses))
            stmt = stmt.where(SchedulingRequest.status.in_(selected_statuses))
    if from_dt:
        count_stmt = count_stmt.where(SchedulingRequest.created_at >= from_dt)
        stmt = stmt.where(SchedulingRequest.created_at >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(SchedulingRequest.created_at <= to_dt)
        stmt = stmt.where(SchedulingRequest.created_at <= to_dt)
    if cursor_key:
        stmt = stmt.where(SchedulingRequest.created_at <= cursor_key[0])

    rows = session.exec(stmt.order_by(SchedulingRequest.created_at.desc()).limit(source_limit)).all()
    return list(rows), _count(session, count_stmt)


def _fetch_call_sessions(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_types: set[str] | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor_key: tuple[datetime, str] | None,
    source_limit: int,
) -> tuple[list[tuple[CallSession, CallRequest]], int]:
    if event_types and not event_types.intersection(
        {"call", "call_session", "call_initiated", "call_completed", "telephony", "voice"}
    ):
        return [], 0

    timestamp_col = func.coalesce(CallSession.twilio_status_updated_at, CallSession.created_at)
    count_stmt = (
        select(func.count(CallSession.id))
        .select_from(CallSession)
        .join(CallRequest, CallSession.call_request_id == CallRequest.id)
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .where(CallRequest.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    stmt = (
        select(CallSession, CallRequest)
        .join(CallRequest, CallSession.call_request_id == CallRequest.id)
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .where(CallRequest.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    if campaign_id:
        count_stmt = count_stmt.where(CallRequest.campaign_id == campaign_id)
        stmt = stmt.where(CallRequest.campaign_id == campaign_id)
    if from_dt:
        count_stmt = count_stmt.where(timestamp_col >= from_dt)
        stmt = stmt.where(timestamp_col >= from_dt)
    if to_dt:
        count_stmt = count_stmt.where(timestamp_col <= to_dt)
        stmt = stmt.where(timestamp_col <= to_dt)
    if cursor_key:
        stmt = stmt.where(timestamp_col <= cursor_key[0])

    rows = session.exec(stmt.order_by(timestamp_col.desc()).limit(source_limit)).all()
    return list(rows), _count(session, count_stmt)


def _find_call_session(
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
    campaign_id: uuid.UUID | None = None,
    call_session_id: uuid.UUID | None = None,
    call_request_id: uuid.UUID | None = None,
) -> tuple[CallSession, CallRequest] | None:
    stmt = (
        select(CallSession, CallRequest)
        .join(CallRequest, CallSession.call_request_id == CallRequest.id)
        .join(Campaign, CallRequest.campaign_id == Campaign.id)
        .where(CallRequest.contact_id == contact_id, Campaign.workspace_id == workspace_id)
    )
    if campaign_id:
        stmt = stmt.where(CallRequest.campaign_id == campaign_id)
    if call_session_id:
        stmt = stmt.where(CallSession.id == call_session_id)
    if call_request_id:
        stmt = stmt.where(CallRequest.id == call_request_id)
    return session.exec(stmt.order_by(CallSession.created_at.desc())).first()


def _find_transcript_excerpt(
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
    campaign_id: uuid.UUID,
    metadata: dict[str, Any] | None,
) -> str | None:
    call_session_id: uuid.UUID | None = None
    call_request_id: uuid.UUID | None = None
    for key in ("call_session_id", "callSessionId"):
        raw = _metadata_value(metadata, key)
        if raw:
            try:
                call_session_id = uuid.UUID(raw)
            except ValueError:
                pass
    for key in ("call_request_id", "callRequestId"):
        raw = _metadata_value(metadata, key)
        if raw:
            try:
                call_request_id = uuid.UUID(raw)
            except ValueError:
                pass

    found = _find_call_session(
        session,
        contact_id=contact_id,
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        call_session_id=call_session_id,
        call_request_id=call_request_id,
    )
    if not found:
        return None
    call_session, _request = found
    return _transcript_excerpt(call_session.transcript)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_contact_timeline(
    *,
    session: Session,
    request: Request,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    page: int,
    limit: int,
    event_type: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
    cursor: str | None = None,
) -> TimelinePagePublic:
    """Aggregate timeline events, sort by timestamp/id, and return one page."""
    event_types = _event_type_values(event_type)
    cursor_key = _decode_cursor(cursor)
    is_first_page = page == 1 and not cursor and not event_types and not from_dt and not to_dt
    cache_key = _cache_key(contact_id, campaign_id)

    if is_first_page:
        cached = await _get_cached(request, cache_key)
        if cached is not None:
            cached_events = [TimelineEventPublic(**item) for item in cached.get("data", [])]
            sliced = cached_events[:limit]
            has_more = int(cached.get("count", len(cached_events))) > len(sliced)
            return TimelinePagePublic(
                data=sliced,
                count=int(cached.get("count", len(cached_events))),
                next_cursor=_encode_cursor(sliced[-1]) if has_more and sliced else None,
            )

    offset = 0 if cursor_key else (page - 1) * limit
    source_limit = 201 if is_first_page else offset + limit + 1

    csh_rows, csh_count = _fetch_state_history(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )
    ce_rows, ce_count = _fetch_contact_events(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )
    rd_rows, rd_count = _fetch_routing_decisions(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )
    sig_rows, sig_count = _fetch_signal_events(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )
    sched_rows, sched_count = _fetch_scheduling_requests(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )
    call_rows, call_count = _fetch_call_sessions(
        session, contact_id, campaign_id, workspace_id, event_types, from_dt, to_dt, cursor_key, source_limit
    )

    events: list[TimelineEventPublic] = (
        [_csh_to_event(row) for row in csh_rows]
        + [_ce_to_event(row) for row in ce_rows]
        + [_rd_to_event(row) for row in rd_rows]
        + [_signal_to_event(row) for row in sig_rows]
        + [_scheduling_to_event(row) for row in sched_rows]
        + [_call_to_event(call_session, call_request) for call_session, call_request in call_rows]
    )
    events.sort(key=_event_sort_key, reverse=True)

    if cursor_key:
        events = [event for event in events if _event_sort_key(event) < cursor_key]

    total = csh_count + ce_count + rd_count + sig_count + sched_count + call_count
    page_events = events[offset : offset + limit]
    has_more = total > offset + len(page_events)
    next_cursor = _encode_cursor(page_events[-1]) if has_more and page_events else None

    if is_first_page:
        await _set_cached(
            request,
            cache_key,
            {"data": [event.model_dump() for event in events[:200]], "count": total},
        )

    return TimelinePagePublic(data=page_events, count=total, next_cursor=next_cursor)


def get_timeline_event_detail(
    *,
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
    event_id: str,
) -> TimelineEventDetailPublic | None:
    """Return full detail for a single timeline entry."""
    prefix, row_id = _parse_prefixed_id(event_id)

    if prefix == _CSH:
        row = session.exec(
            select(ContactStateHistory)
            .join(Campaign, ContactStateHistory.campaign_id == Campaign.id)
            .where(
                ContactStateHistory.id == row_id,
                ContactStateHistory.contact_id == contact_id,
                Campaign.workspace_id == workspace_id,
            )
        ).first()
        if not row:
            return None
        base = _csh_to_event(row)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            reason_code_explanation=_reason_code_explanation(row.reason),
        )

    if prefix == _CE:
        row = session.get(ContactEvent, row_id)
        if not row or row.contact_id != contact_id or row.workspace_id != workspace_id:
            return None
        base = _ce_to_event(row)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            reason_code_explanation=_reason_code_explanation(row.reason_code, row.event_metadata),
            transcript_excerpt=(
                _find_transcript_excerpt(session, contact_id, workspace_id, row.campaign_id, row.event_metadata)
                if row.channel in {"voice", "call", "telephony"}
                else None
            ),
        )

    if prefix == _RD:
        row = session.get(RoutingDecision, row_id)
        if not row or row.contact_id != contact_id or row.workspace_id != workspace_id:
            return None
        base = _rd_to_event(row)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            rule_name=row.rule_name,
            rule_condition=row.rule_condition,
            signal_summary=row.signal_summary,
            reason_code_explanation=_reason_code_explanation(
                row.reason_code,
                fallback=row.signal_summary or row.rule_condition,
            ),
        )

    if prefix == _SIG:
        row = session.exec(
            select(SignalEvent)
            .join(Campaign, SignalEvent.campaign_id == Campaign.id)
            .where(
                SignalEvent.id == row_id,
                SignalEvent.contact_id == contact_id,
                Campaign.workspace_id == workspace_id,
            )
        ).first()
        if not row:
            return None
        base = _signal_to_event(row)
        signal_summary = _metadata_value(row.signal_metadata, "summary", "signal_summary")
        return TimelineEventDetailPublic(
            **base.model_dump(),
            signal_summary=signal_summary,
            reason_code_explanation=_reason_code_explanation(
                row.signal_type,
                row.signal_metadata,
                fallback=f"{row.signal_type.replace('_', ' ')} detected with {row.confidence:.0%} confidence.",
            ),
        )

    if prefix == _SCHED:
        row = session.exec(
            select(SchedulingRequest)
            .join(Campaign, SchedulingRequest.campaign_id == Campaign.id)
            .where(
                SchedulingRequest.id == row_id,
                SchedulingRequest.contact_id == contact_id,
                Campaign.workspace_id == workspace_id,
            )
        ).first()
        if not row:
            return None
        base = _scheduling_to_event(row)
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            reason_code_explanation=f"Scheduling request is currently {status}.",
        )

    if prefix == _CALL:
        found = _find_call_session(
            session,
            contact_id=contact_id,
            workspace_id=workspace_id,
            call_session_id=row_id,
        )
        if not found:
            return None
        call_session, call_request = found
        base = _call_to_event(call_session, call_request)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            transcript_excerpt=_transcript_excerpt(call_session.transcript),
            signal_summary=(
                json.dumps(call_session.unanswered_questions)
                if call_session.unanswered_questions
                else None
            ),
            reason_code_explanation=_reason_code_explanation(call_request.trigger_reason),
        )

    return None
