"""Timeline aggregation service for contact explainability (Story 5.1)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlmodel import Session

from app.domain_models import (
    ContactEvent,
    ContactStateHistory,
    RoutingDecision,
    TimelineEventDetailPublic,
    TimelineEventPublic,
    TimelinePagePublic,
)

# Source-system prefix → table identifier
_CSH = "csh"
_CE = "ce"
_RD = "rd"

TIMELINE_CACHE_TTL = 30  # seconds
_CACHE_KEY = "timeline:{contact_id}:{campaign_id or 'all'}:page1"


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
        has_detail=False,
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
        has_detail=False,
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
        has_detail=bool(row.rule_condition or row.signal_summary),
    )


def _parse_prefixed_id(prefixed_id: str) -> tuple[str, uuid.UUID]:
    """Parse 'csh_<hex>' → ('csh', UUID). Raises ValueError on bad format."""
    parts = prefixed_id.split("_", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid event id format: {prefixed_id!r}")
    prefix, hex_str = parts
    return prefix, uuid.UUID(hex_str)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_key(contact_id: uuid.UUID, campaign_id: uuid.UUID | None) -> str:
    campaign_part = campaign_id.hex if campaign_id else "all"
    return f"timeline:{contact_id.hex}:{campaign_part}:page1"


async def _get_cached(request: Request, key: str) -> list[dict[str, Any]] | None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return None
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception:  # noqa: BLE001
        pass
    return None


async def _set_cached(request: Request, key: str, data: list[dict[str, Any]]) -> None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return
        await redis.setex(key, TIMELINE_CACHE_TTL, json.dumps(data, default=str))
    except Exception:  # noqa: BLE001
        pass


async def invalidate_timeline_cache(
    request: Request,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None = None,
) -> None:
    """Invalidate the first-page cache on new event write."""
    key = _cache_key(contact_id, campaign_id)
    try:
        redis = request.app.state.redis_manager.client
        if redis:
            await redis.delete(key)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _fetch_state_history(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_type_filter: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[ContactStateHistory]:
    if event_type_filter and event_type_filter != "state_transition":
        return []
    stmt = session.query(ContactStateHistory).filter(
        ContactStateHistory.contact_id == contact_id,
    )
    if campaign_id:
        stmt = stmt.filter(ContactStateHistory.campaign_id == campaign_id)
    if from_dt:
        stmt = stmt.filter(ContactStateHistory.triggered_at >= from_dt)
    if to_dt:
        stmt = stmt.filter(ContactStateHistory.triggered_at <= to_dt)
    return stmt.all()


def _fetch_contact_events(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_type_filter: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[ContactEvent]:
    stmt = session.query(ContactEvent).filter(
        ContactEvent.contact_id == contact_id,
        ContactEvent.workspace_id == workspace_id,
    )
    if campaign_id:
        stmt = stmt.filter(ContactEvent.campaign_id == campaign_id)
    if event_type_filter:
        stmt = stmt.filter(ContactEvent.event_type == event_type_filter)
    if from_dt:
        stmt = stmt.filter(ContactEvent.created_at >= from_dt)
    if to_dt:
        stmt = stmt.filter(ContactEvent.created_at <= to_dt)
    return stmt.all()


def _fetch_routing_decisions(
    session: Session,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID | None,
    workspace_id: str,
    event_type_filter: str | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[RoutingDecision]:
    stmt = session.query(RoutingDecision).filter(
        RoutingDecision.contact_id == contact_id,
        RoutingDecision.workspace_id == workspace_id,
    )
    if campaign_id:
        stmt = stmt.filter(RoutingDecision.campaign_id == campaign_id)
    if event_type_filter:
        stmt = stmt.filter(RoutingDecision.decision_type == event_type_filter)
    if from_dt:
        stmt = stmt.filter(RoutingDecision.created_at >= from_dt)
    if to_dt:
        stmt = stmt.filter(RoutingDecision.created_at <= to_dt)
    return stmt.all()


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
) -> TimelinePagePublic:
    """Aggregate events from all sources, sort by timestamp, paginate."""
    is_first_page = (page == 1 and not event_type and not from_dt and not to_dt)
    cache_key = _cache_key(contact_id, campaign_id)

    # Serve from cache only for unfiltered first page
    if is_first_page:
        cached = await _get_cached(request, cache_key)
        if cached is not None:
            sliced = cached[:limit]
            return TimelinePagePublic(
                data=[TimelineEventPublic(**item) for item in sliced],
                count=len(cached),
                next_cursor=None if len(cached) <= limit else f"{limit + 1}",
            )

    # Fetch from all three sources
    csh_rows = _fetch_state_history(session, contact_id, campaign_id, workspace_id, event_type, from_dt, to_dt)
    ce_rows = _fetch_contact_events(session, contact_id, campaign_id, workspace_id, event_type, from_dt, to_dt)
    rd_rows = _fetch_routing_decisions(session, contact_id, campaign_id, workspace_id, event_type, from_dt, to_dt)

    events: list[TimelineEventPublic] = (
        [_csh_to_event(r) for r in csh_rows]
        + [_ce_to_event(r) for r in ce_rows]
        + [_rd_to_event(r) for r in rd_rows]
    )

    events.sort(key=lambda e: e.timestamp, reverse=True)

    total = len(events)

    if is_first_page:
        # Cache full unfiltered list (up to 200 events) for 30s
        await _set_cached(request, cache_key, [e.model_dump() for e in events[:200]])

    offset = (page - 1) * limit
    page_events = events[offset : offset + limit]

    has_more = (offset + limit) < total
    next_cursor = str(offset + limit + 1) if has_more else None

    return TimelinePagePublic(data=page_events, count=total, next_cursor=next_cursor)


def get_timeline_event_detail(
    *,
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
    event_id: str,
) -> TimelineEventDetailPublic:
    """Return full detail for a single timeline entry."""
    prefix, row_id = _parse_prefixed_id(event_id)

    if prefix == _CSH:
        row = session.get(ContactStateHistory, row_id)
        if not row or row.contact_id != contact_id:
            return None  # type: ignore[return-value]
        base = _csh_to_event(row)
        return TimelineEventDetailPublic(**base.model_dump())

    if prefix == _CE:
        row = session.get(ContactEvent, row_id)
        if not row or row.contact_id != contact_id or row.workspace_id != workspace_id:
            return None  # type: ignore[return-value]
        base = _ce_to_event(row)
        return TimelineEventDetailPublic(**base.model_dump())

    if prefix == _RD:
        row = session.get(RoutingDecision, row_id)
        if not row or row.contact_id != contact_id or row.workspace_id != workspace_id:
            return None  # type: ignore[return-value]
        base = _rd_to_event(row)
        return TimelineEventDetailPublic(
            **base.model_dump(),
            rule_name=row.rule_name,
            rule_condition=row.rule_condition,
            signal_summary=row.signal_summary,
        )

    return None  # type: ignore[return-value]
