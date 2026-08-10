"""Nightly KPI snapshot job for SignalLoop.

Runs once per day (scheduled externally at 02:00 UTC) and materialises
yesterday's KPI counters from the operational tables (action_queue,
routing_decisions) into kpi_daily_snapshots.

Runs one row per (workspace_id, campaign_id) combination that had activity
on the target date.  Uses INSERT ... ON CONFLICT DO UPDATE for idempotency
so it is safe to re-run.
"""
from __future__ import annotations

import logging
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path bootstrap — allows running the file directly from the repo root
# even when ``app`` (apps/api) is not yet installed as an editable package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[5]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain_models import ActionQueue, KpiDailySnapshot, RoutingDecision  # noqa: E402
from app.domain.reporting.kpi_aggregation_service import compute_daily_snapshot  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("nightly_kpi_snapshot_job")


def _active_workspace_campaign_pairs(session: Session, target_date: date) -> list[tuple[str, uuid.UUID | None]]:
    """Return distinct (workspace_id, campaign_id) pairs that had activity on target_date."""
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, 999999, tzinfo=timezone.utc)

    stmt = (
        select(ActionQueue.workspace_id, ActionQueue.campaign_id)
        .where(ActionQueue.created_at >= day_start, ActionQueue.created_at <= day_end)
        .distinct()
    )
    rows = session.exec(stmt).all()

    # Also include pairs with routing decisions
    rd_stmt = (
        select(RoutingDecision.workspace_id, RoutingDecision.campaign_id)
        .where(RoutingDecision.created_at >= day_start, RoutingDecision.created_at <= day_end)
        .distinct()
    )
    rd_rows = session.exec(rd_stmt).all()

    combined: set[tuple[str, uuid.UUID | None]] = set()
    for ws, cid in rows:
        combined.add((str(ws), uuid.UUID(str(cid)) if cid else None))
    for ws, cid in rd_rows:
        combined.add((str(ws), uuid.UUID(str(cid)) if cid else None))

    return list(combined)


def _upsert_snapshot(session: Session, snapshot: KpiDailySnapshot) -> None:
    """Insert snapshot row; update counters if a row already exists for the same
    (workspace_id, campaign_id, date) combination."""
    existing = session.exec(
        select(KpiDailySnapshot).where(
            KpiDailySnapshot.workspace_id == snapshot.workspace_id,
            KpiDailySnapshot.campaign_id == snapshot.campaign_id,
            KpiDailySnapshot.date == snapshot.date,
        )
    ).first()

    if existing is None:
        session.add(snapshot)
    else:
        existing.contacts_processed = snapshot.contacts_processed
        existing.intent_signals = snapshot.intent_signals
        existing.qualified_contacts = snapshot.qualified_contacts
        existing.bookings_confirmed = snapshot.bookings_confirmed
        existing.provider_errors = snapshot.provider_errors
        existing.booking_sla_met = snapshot.booking_sla_met
        existing.booking_sla_breached = snapshot.booking_sla_breached
        session.add(existing)


def _invalidate_redis_cache(affected_workspaces: set[str]) -> None:
    """Delete Redis KPI cache keys for all affected workspaces.

    Uses a pattern scan so it degrades gracefully if the Redis client
    is unavailable (just logs a warning).
    """
    try:
        import asyncio  # noqa: PLC0415

        import redis.asyncio as aioredis  # noqa: PLC0415

        from app.core.config import settings  # noqa: PLC0415

        async def _purge() -> None:
            client = aioredis.Redis.from_url(
                settings.REDIS_URL, encoding="utf-8", decode_responses=True
            )
            try:
                for ws_id in affected_workspaces:
                    pattern = f"kpi:{ws_id}:*"
                    keys = await client.keys(pattern)
                    if keys:
                        await client.delete(*keys)
                        log.info("Purged %d cache keys for workspace %s", len(keys), ws_id)
            finally:
                await client.aclose()

        asyncio.run(_purge())
    except Exception as exc:  # noqa: BLE001
        log.warning("Redis cache invalidation failed (non-fatal): %s", exc)


def run(target_date: date | None = None) -> None:
    if target_date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    log.info("Starting nightly KPI snapshot job for date=%s", target_date)
    affected_workspaces: set[str] = set()

    with Session(engine) as session:
        pairs = _active_workspace_campaign_pairs(session, target_date)
        log.info("Found %d (workspace, campaign) pairs with activity on %s", len(pairs), target_date)

        for workspace_id, campaign_id in pairs:
            try:
                snapshot = compute_daily_snapshot(session, target_date, workspace_id, campaign_id)
                _upsert_snapshot(session, snapshot)
                affected_workspaces.add(workspace_id)
            except Exception as exc:  # noqa: BLE001
                log.error(
                    "Failed to compute snapshot for ws=%s campaign=%s date=%s: %s",
                    workspace_id,
                    campaign_id,
                    target_date,
                    exc,
                    exc_info=True,
                )

        session.commit()

    log.info("Committed %d snapshots. Invalidating Redis KPI cache.", len(pairs))
    _invalidate_redis_cache(affected_workspaces)
    log.info("Nightly KPI snapshot job complete for date=%s", target_date)


if __name__ == "__main__":
    run()
