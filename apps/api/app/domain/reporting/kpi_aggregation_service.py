"""KPI aggregation service — reads from kpi_daily_snapshots for historical queries
and performs live aggregation only for today's partial day window.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import func
from sqlmodel import Session, select

from app.domain_models import (
    ActionQueue,
    Campaign,
    KpiDailySnapshot,
    RoutingDecision,
)

Granularity = Literal["weekly", "biweekly", "monthly"]

_BUCKET_DAYS: dict[Granularity, int] = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}


# ---------------------------------------------------------------------------
# Snapshot-based aggregation helpers
# ---------------------------------------------------------------------------


def _agg_snapshots(
    session: Session,
    workspace_id: str,
    start: date,
    end: date,
    campaign_id: uuid.UUID | None,
) -> dict:
    """Sum all KPI counters from materialized snapshots for a given date range."""
    stmt = select(
        func.coalesce(func.sum(KpiDailySnapshot.contacts_processed), 0),
        func.coalesce(func.sum(KpiDailySnapshot.intent_signals), 0),
        func.coalesce(func.sum(KpiDailySnapshot.qualified_contacts), 0),
        func.coalesce(func.sum(KpiDailySnapshot.bookings_confirmed), 0),
        func.coalesce(func.sum(KpiDailySnapshot.provider_errors), 0),
        func.coalesce(func.sum(KpiDailySnapshot.booking_sla_met), 0),
        func.coalesce(func.sum(KpiDailySnapshot.booking_sla_breached), 0),
    ).where(
        KpiDailySnapshot.workspace_id == workspace_id,
        KpiDailySnapshot.date >= datetime(start.year, start.month, start.day, tzinfo=None),
        KpiDailySnapshot.date <= datetime(end.year, end.month, end.day, tzinfo=None),
    )
    if campaign_id is not None:
        stmt = stmt.where(KpiDailySnapshot.campaign_id == campaign_id)
    row = session.exec(stmt).first()
    if row is None:
        return _zero_kpi()
    (
        contacts_processed,
        intent_signals,
        qualified_contacts,
        bookings_confirmed,
        provider_errors,
        booking_sla_met,
        booking_sla_breached,
    ) = row
    return _compute_kpi(
        int(contacts_processed),
        int(intent_signals),
        int(qualified_contacts),
        int(bookings_confirmed),
        int(provider_errors),
        int(booking_sla_met),
        int(booking_sla_breached),
    )


# ---------------------------------------------------------------------------
# Live aggregation for today's partial window
# ---------------------------------------------------------------------------


def _ensure_campaign_workspace(
    session: Session, workspace_id: str, campaign_id: uuid.UUID | None
) -> None:
    if campaign_id is None:
        return
    campaign = session.get(Campaign, campaign_id)
    if campaign is None or campaign.workspace_id != workspace_id:
        raise ValueError("campaign workspace mismatch")


def _agg_today_live(
    session: Session,
    workspace_id: str,
    campaign_id: uuid.UUID | None,
) -> dict:
    """Compute today's partial KPIs live from operational tables."""
    _ensure_campaign_workspace(session, workspace_id, campaign_id)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = datetime.now(timezone.utc)

    # contacts_processed: distinct contacts touched by action_queue today
    contacts_stmt = select(func.count(func.distinct(ActionQueue.contact_id))).where(
        ActionQueue.created_at >= today_start,
        ActionQueue.created_at <= today_end,
        ActionQueue.workspace_id == workspace_id,
    )
    if campaign_id is not None:
        contacts_stmt = contacts_stmt.where(ActionQueue.campaign_id == campaign_id)

    # We need to filter by workspace — join to Campaign for workspace_id
    contacts_stmt = contacts_stmt.join(
        Campaign, ActionQueue.campaign_id == Campaign.id
    ).where(Campaign.workspace_id == workspace_id)

    contacts_processed = session.exec(contacts_stmt).first() or 0

    # intent_signals: routing decisions with decision_type = "intent_detected" today
    signals_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.decision_type == "intent_detected",
        RoutingDecision.created_at >= today_start,
        RoutingDecision.created_at <= today_end,
    )
    if campaign_id is not None:
        signals_stmt = signals_stmt.where(RoutingDecision.campaign_id == campaign_id)
    intent_signals = session.exec(signals_stmt).first() or 0

    # qualified_contacts: routing decisions with outcome = "qualified"
    qualified_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.outcome == "qualified",
        RoutingDecision.created_at >= today_start,
        RoutingDecision.created_at <= today_end,
    )
    if campaign_id is not None:
        qualified_stmt = qualified_stmt.where(RoutingDecision.campaign_id == campaign_id)
    qualified_contacts = session.exec(qualified_stmt).first() or 0

    # bookings_confirmed: routing decisions with outcome = "booked"
    bookings_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.outcome == "booked",
        RoutingDecision.created_at >= today_start,
        RoutingDecision.created_at <= today_end,
    )
    if campaign_id is not None:
        bookings_stmt = bookings_stmt.where(RoutingDecision.campaign_id == campaign_id)
    bookings_confirmed = session.exec(bookings_stmt).first() or 0

    # provider_errors: failed action_queue rows
    errors_stmt = select(func.count(ActionQueue.id)).join(
        Campaign, ActionQueue.campaign_id == Campaign.id
    ).where(
        Campaign.workspace_id == workspace_id,
        ActionQueue.workspace_id == workspace_id,
        ActionQueue.status == "failed",
        ActionQueue.created_at >= today_start,
        ActionQueue.created_at <= today_end,
    )
    if campaign_id is not None:
        errors_stmt = errors_stmt.where(ActionQueue.campaign_id == campaign_id)
    provider_errors = session.exec(errors_stmt).first() or 0

    return _compute_kpi(
        int(contacts_processed),
        int(intent_signals),
        int(qualified_contacts),
        int(bookings_confirmed),
        int(provider_errors),
        booking_sla_met=0,
        booking_sla_breached=0,
    )


# ---------------------------------------------------------------------------
# Bucketed trend aggregation
# ---------------------------------------------------------------------------


def get_kpi_trend(
    session: Session,
    workspace_id: str,
    start: date,
    end: date,
    granularity: Granularity,
    campaign_id: uuid.UUID | None = None,
) -> list[dict]:
    """Return bucketed KPI data points between start and end (inclusive)."""
    bucket_days = _BUCKET_DAYS[granularity]
    buckets: list[dict] = []
    current = start
    today = date.today()

    while current <= end:
        bucket_end = min(current + timedelta(days=bucket_days - 1), end)

        if bucket_end < today:
            # Entirely historical — use materialized snapshots
            kpi = _agg_snapshots(session, workspace_id, current, bucket_end, campaign_id)
        elif current == today:
            # Entirely today — live aggregation
            kpi = _agg_today_live(session, workspace_id, campaign_id)
        else:
            # Bucket spans past + today: combine
            past_end = today - timedelta(days=1)
            kpi_past = _agg_snapshots(session, workspace_id, current, past_end, campaign_id)
            kpi_live = _agg_today_live(session, workspace_id, campaign_id)
            kpi = _merge_kpis(kpi_past, kpi_live)

        buckets.append({"period_start": str(current), "period_end": str(bucket_end), **kpi})
        current = bucket_end + timedelta(days=1)

    return buckets


# ---------------------------------------------------------------------------
# Period-over-period delta
# ---------------------------------------------------------------------------


def get_kpi_summary(
    session: Session,
    workspace_id: str,
    start: date,
    end: date,
    _granularity: Granularity,
    campaign_id: uuid.UUID | None = None,
) -> dict:
    """Return current_period KPIs, prior_period KPIs, and delta_pct for each metric."""
    period_days = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=period_days - 1)

    today = date.today()

    if end < today:
        current_kpi = _agg_snapshots(session, workspace_id, start, end, campaign_id)
    elif start == today:
        current_kpi = _agg_today_live(session, workspace_id, campaign_id)
    else:
        past_kpi = _agg_snapshots(session, workspace_id, start, today - timedelta(days=1), campaign_id)
        live_kpi = _agg_today_live(session, workspace_id, campaign_id)
        current_kpi = _merge_kpis(past_kpi, live_kpi)

    prior_kpi = _agg_snapshots(session, workspace_id, prior_start, prior_end, campaign_id)

    delta_pct: dict[str, float | None] = {}
    for metric in current_kpi:
        curr_val = current_kpi.get(metric)
        prior_val = prior_kpi.get(metric)
        if curr_val is not None and prior_val not in (None, 0):
            delta_pct[metric] = round(((curr_val or 0) - prior_val) / prior_val * 100, 2)
        else:
            delta_pct[metric] = None

    return {
        "current_period": {"start": str(start), "end": str(end), **current_kpi},
        "prior_period": {"start": str(prior_start), "end": str(prior_end), **prior_kpi},
        "delta_pct": delta_pct,
    }


# ---------------------------------------------------------------------------
# Nightly snapshot computation (called by the nightly job)
# ---------------------------------------------------------------------------


def compute_daily_snapshot(
    session: Session,
    target_date: date,
    workspace_id: str,
    campaign_id: uuid.UUID | None,
) -> KpiDailySnapshot:
    """Aggregate one day's KPIs from operational tables and return a snapshot row."""
    _ensure_campaign_workspace(session, workspace_id, campaign_id)
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    contacts_stmt = select(func.count(func.distinct(ActionQueue.contact_id))).join(
        Campaign, ActionQueue.campaign_id == Campaign.id
    ).where(
        Campaign.workspace_id == workspace_id,
        ActionQueue.workspace_id == workspace_id,
        ActionQueue.created_at >= day_start,
        ActionQueue.created_at <= day_end,
    )
    if campaign_id is not None:
        contacts_stmt = contacts_stmt.where(ActionQueue.campaign_id == campaign_id)
    contacts_processed = int(session.exec(contacts_stmt).first() or 0)

    signals_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.decision_type == "intent_detected",
        RoutingDecision.created_at >= day_start,
        RoutingDecision.created_at <= day_end,
    )
    if campaign_id is not None:
        signals_stmt = signals_stmt.where(RoutingDecision.campaign_id == campaign_id)
    intent_signals = int(session.exec(signals_stmt).first() or 0)

    qualified_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.outcome == "qualified",
        RoutingDecision.created_at >= day_start,
        RoutingDecision.created_at <= day_end,
    )
    if campaign_id is not None:
        qualified_stmt = qualified_stmt.where(RoutingDecision.campaign_id == campaign_id)
    qualified_contacts = int(session.exec(qualified_stmt).first() or 0)

    bookings_stmt = select(func.count(RoutingDecision.id)).where(
        RoutingDecision.workspace_id == workspace_id,
        RoutingDecision.outcome == "booked",
        RoutingDecision.created_at >= day_start,
        RoutingDecision.created_at <= day_end,
    )
    if campaign_id is not None:
        bookings_stmt = bookings_stmt.where(RoutingDecision.campaign_id == campaign_id)
    bookings_confirmed = int(session.exec(bookings_stmt).first() or 0)

    errors_stmt = select(func.count(ActionQueue.id)).join(
        Campaign, ActionQueue.campaign_id == Campaign.id
    ).where(
        Campaign.workspace_id == workspace_id,
        ActionQueue.workspace_id == workspace_id,
        ActionQueue.status == "failed",
        ActionQueue.created_at >= day_start,
        ActionQueue.created_at <= day_end,
    )
    if campaign_id is not None:
        errors_stmt = errors_stmt.where(ActionQueue.campaign_id == campaign_id)
    provider_errors = int(session.exec(errors_stmt).first() or 0)

    return KpiDailySnapshot(
        date=datetime(target_date.year, target_date.month, target_date.day),
        workspace_id=workspace_id,
        campaign_id=campaign_id,
        contacts_processed=contacts_processed,
        intent_signals=intent_signals,
        qualified_contacts=qualified_contacts,
        bookings_confirmed=bookings_confirmed,
        provider_errors=provider_errors,
        booking_sla_met=0,
        booking_sla_breached=0,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _zero_kpi() -> dict:
    return _compute_kpi(0, 0, 0, 0, 0, 0, 0)


def _compute_kpi(
    contacts_processed: int,
    intent_signals: int,
    qualified_contacts: int,
    bookings_confirmed: int,
    provider_errors: int,
    booking_sla_met: int,
    booking_sla_breached: int,
) -> dict:
    signal_yield_rate = (
        round(intent_signals / contacts_processed * 100, 2) if contacts_processed else 0.0
    )
    conversion_rate = (
        round(bookings_confirmed / qualified_contacts * 100, 2) if qualified_contacts else 0.0
    )
    sla_total = booking_sla_met + booking_sla_breached
    booking_sla_compliance_pct = (
        round(booking_sla_met / sla_total * 100, 2) if sla_total else None
    )
    return {
        "contacts_processed": contacts_processed,
        "intent_signals": intent_signals,
        "qualified_contacts": qualified_contacts,
        "bookings_confirmed": bookings_confirmed,
        "provider_errors": provider_errors,
        "booking_sla_met": booking_sla_met,
        "booking_sla_breached": booking_sla_breached,
        "signal_yield_rate": signal_yield_rate,
        "conversion_rate": conversion_rate,
        "booking_sla_compliance_pct": booking_sla_compliance_pct,
    }


def _merge_kpis(a: dict, b: dict) -> dict:
    return _compute_kpi(
        int(a.get("contacts_processed", 0)) + int(b.get("contacts_processed", 0)),
        int(a.get("intent_signals", 0)) + int(b.get("intent_signals", 0)),
        int(a.get("qualified_contacts", 0)) + int(b.get("qualified_contacts", 0)),
        int(a.get("bookings_confirmed", 0)) + int(b.get("bookings_confirmed", 0)),
        int(a.get("provider_errors", 0)) + int(b.get("provider_errors", 0)),
        int(a.get("booking_sla_met", 0)) + int(b.get("booking_sla_met", 0)),
        int(a.get("booking_sla_breached", 0)) + int(b.get("booking_sla_breached", 0)),
    )
