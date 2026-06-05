"""Scheduled call worker — polls for QUEUED CallRequests and initiates via Twilio.

Poll cycle: every 30 s via APScheduler AsyncIOScheduler.

Per cycle:
  1. Enforce daily call cap per workspace (read from GovernancePolicy; default 50).
     If cap is reached, skip the entire cycle.
  2. Fetch up to BATCH_SIZE QUEUED CallRequests ordered by trigger_reason priority
     then created_at ASC (FIFO).  The CallRequest model has no 'priority' column, so
     trigger_reason is mapped: manual_queue(1) > positive_email_signal(2) > others(3).
  3. For each candidate: check the contact's local timezone (09:00–18:00); skip if
     outside call hours (row stays QUEUED for the next cycle).
  4. Resolve Twilio credentials via credential_resolver for the contact's workspace.
  5. Initiate the call via TwilioVoiceAdapter.initiate_call().
  6. On success: set CallRequest.status = in_progress, store twilio_call_sid on
     CallSession, write an audit_event row.
  7. On Twilio error: set CallRequest.status = failed, record outcome on CallSession,
     write an audit_event row.
"""
from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import case, func
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.domain.audit.audit_events import AuditEvent
from app.domain.providers.credential_resolver import resolve_provider_credentials
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
)
from app.domain_models import (
    Contact,
    GovernancePolicy,
    NotificationProvider,
    PolicyStatus,
    PolicyType,
)
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter
from app.infrastructure.providers.base import VoiceAdapter
from app.infrastructure.providers.registry import resolve_voice_adapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL_SECONDS: int = 30
DEFAULT_DAILY_CALL_CAP: int = 50
BATCH_SIZE: int = 5
_CALL_START_HOUR: int = 9   # 09:00 inclusive (local time)
_CALL_END_HOUR: int = 18    # 18:00 exclusive  (local time)

# Engine is created once at module load; the settings object reads from .env.
_engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_tz(tz_name: str | None) -> ZoneInfo:
    """Parse *tz_name* to a ZoneInfo; fall back to UTC on any error."""
    if not tz_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        logger.debug("Unknown timezone %r — falling back to UTC", tz_name)
        return ZoneInfo("UTC")


def _is_within_call_hours(tz: ZoneInfo) -> bool:
    """Return True if the current moment in *tz* falls in [09:00, 18:00)."""
    local_hour = datetime.now(tz).hour
    return _CALL_START_HOUR <= local_hour < _CALL_END_HOUR


def _get_daily_cap(session: Session, workspace_id: str) -> int:
    """Return the active daily_call_cap for *workspace_id*, or the default."""
    policy = session.exec(
        select(GovernancePolicy)
        .where(
            GovernancePolicy.workspace_id == workspace_id,
            GovernancePolicy.policy_type == PolicyType.daily_caps,
            GovernancePolicy.status == PolicyStatus.active,
        )
        .order_by(GovernancePolicy.created_at.desc())  # type: ignore[arg-type]
        .limit(1)
    ).first()

    if policy:
        try:
            cap = int(policy.payload_json.get("daily_call_cap", DEFAULT_DAILY_CALL_CAP))
            return max(1, cap)
        except (TypeError, ValueError):
            pass
    return DEFAULT_DAILY_CALL_CAP


def _today_call_count(session: Session, workspace_id: str) -> int:
    """Count non-failed calls initiated today (UTC) for *workspace_id*."""
    today: date = datetime.now(UTC).date()
    count_val = session.exec(
        select(func.count(CallRequest.id))
        .join(Contact, Contact.id == CallRequest.contact_id)
        .where(
            Contact.workspace_id == workspace_id,
            func.date(CallRequest.created_at) == today,
            CallRequest.status != CallRequestStatus.failed,
        )
    ).one()
    return int(count_val or 0)


def _write_audit_event(
    session: Session,
    *,
    workspace_id: str,
    call_req: CallRequest,
    call_sid: str,
    error: str | None = None,
) -> None:
    """Insert an AuditEvent row into the current session (not yet committed)."""
    payload: dict[str, Any] = {
        "call_request_id": str(call_req.id),
        "contact_id": str(call_req.contact_id),
        "campaign_id": str(call_req.campaign_id),
        "trigger_reason": call_req.trigger_reason,
        "twilio_call_sid": call_sid,
    }
    if error:
        payload["error"] = error

    event = AuditEvent(
        event_name="call.initiated" if not error else "call.failed",
        workspace_id=workspace_id,
        resource_type="CallRequest",
        resource_id=str(call_req.id),
        payload=payload,
    )
    session.add(event)


def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 4:
        return "****"
    return f"****{digits[-4:]}"


# ---------------------------------------------------------------------------
# Per-call dispatch
# ---------------------------------------------------------------------------


async def _initiate_one(
    session: Session,
    call_req: CallRequest,
    workspace_id: str,
    adapter: VoiceAdapter,
) -> bool:
    """Attempt to initiate a single call.

    Mutates *session* objects; the caller is responsible for committing or
    rolling back.  Returns True if the call was successfully handed to Twilio.
    """
    contact = session.get(Contact, call_req.contact_id)
    if not contact:
        logger.warning("Contact %s not found — marking FAILED", call_req.contact_id)
        call_req.status = CallRequestStatus.failed
        _write_audit_event(
            session,
            workspace_id=workspace_id,
            call_req=call_req,
            call_sid="",
            error="contact_not_found",
        )
        session.add(call_req)
        return False

    # Quiet-hours guard (per contact's local timezone)
    tz = _safe_tz(contact.timezone)
    if not _is_within_call_hours(tz):
        logger.debug(
            "call_request=%s outside call hours (contact tz=%s) — deferring",
            call_req.id,
            contact.timezone,
        )
        return False  # leave status QUEUED; no status change needed

    phone = contact.phone
    if not phone:
        logger.warning("Contact %s has no phone number — marking FAILED", contact.id)
        call_req.status = CallRequestStatus.failed
        _write_audit_event(
            session,
            workspace_id=workspace_id,
            call_req=call_req,
            call_sid="",
            error="no_phone_number",
        )
        session.add(call_req)
        return False

    call_session = session.exec(
        select(CallSession)
        .where(CallSession.call_request_id == call_req.id)
        .with_for_update()
    ).first()
    if call_session and call_session.twilio_call_sid:
        logger.info(
            "Call request already dispatched: call_request=%s sid=%s",
            call_req.id,
            call_session.twilio_call_sid,
        )
        call_req.status = CallRequestStatus.in_progress
        session.add(call_req)
        return False

    account_sid = getattr(adapter, "_account_sid", "") or None
    if call_session is None:
        call_session = CallSession(
            call_request_id=call_req.id,
            twilio_account_sid=account_sid,
        )
        session.add(call_session)
        session.flush()  # assign PK
    else:
        call_session.twilio_account_sid = account_sid or call_session.twilio_account_sid

    twiml_url = (
        f"https://{settings.SERVER_HOST}{settings.API_V1_STR}/voice/twiml"
    )
    status_callback_url = (
        f"https://{settings.SERVER_HOST}{settings.API_V1_STR}/voice/status"
    )

    try:
        result = await adapter.initiate_call(
            to=phone,
            twiml_url=twiml_url,
            status_callback_url=status_callback_url,
        )
    except Exception as exc:
        logger.exception("Twilio exception for call_request=%s", call_req.id)
        call_req.status = CallRequestStatus.failed
        call_session.outcome = CallOutcome.failed
        _write_audit_event(
            session,
            workspace_id=workspace_id,
            call_req=call_req,
            call_sid="",
            error=exc.__class__.__name__,
        )
        session.add(call_req)
        session.add(call_session)
        return False

    call_sid = result.get("call_sid", "")
    if call_sid:
        call_session.twilio_call_sid = call_sid
        call_session.twilio_account_sid = account_sid or call_session.twilio_account_sid
        call_session.twilio_status = "initiated"
        call_session.twilio_status_updated_at = datetime.now(UTC)
        call_req.status = CallRequestStatus.in_progress  # INITIATED
        logger.info(
            "Call initiated — contact=%s phone=%s sid=%s trigger=%s",
            contact.id,
            _mask_phone(phone),
            call_sid,
            call_req.trigger_reason,
        )
        _write_audit_event(
            session,
            workspace_id=workspace_id,
            call_req=call_req,
            call_sid=call_sid,
        )
    else:
        error_detail = result.get("error_code") or result.get("error", "twilio_rejected")
        logger.warning(
            "Twilio rejected call for contact=%s: %s", contact.id, error_detail
        )
        call_req.status = CallRequestStatus.failed
        call_session.outcome = CallOutcome.failed
        _write_audit_event(
            session,
            workspace_id=workspace_id,
            call_req=call_req,
            call_sid="",
            error=error_detail,
        )

    session.add(call_req)
    session.add(call_session)
    return bool(call_sid)


# ---------------------------------------------------------------------------
# Poll cycle
# ---------------------------------------------------------------------------


async def poll_and_dispatch() -> None:
    """One poll cycle: enforce caps, fetch a batch of QUEUED calls, dispatch."""
    workspace_id = settings.DEFAULT_WORKSPACE_ID

    with Session(_engine) as session:
        # ------------------------------------------------------------------
        # 1. Daily cap check (skip entire cycle if reached)
        # ------------------------------------------------------------------
        daily_cap = _get_daily_cap(session, workspace_id)
        today_count = _today_call_count(session, workspace_id)

        if today_count >= daily_cap:
            logger.warning(
                "Daily call cap reached (%d/%d) — skipping poll cycle",
                today_count,
                daily_cap,
            )
            return

        remaining_budget = min(BATCH_SIZE, daily_cap - today_count)

        # ------------------------------------------------------------------
        # 2. Fetch candidates ordered by trigger_reason priority, then FIFO.
        #    No 'priority' column exists; map trigger_reason to an ordinal.
        # ------------------------------------------------------------------
        priority_expr = case(
            (CallRequest.trigger_reason == "manual_queue", 1),
            (CallRequest.trigger_reason == "positive_email_signal", 2),
            else_=3,
        )

        candidates = session.exec(
            select(CallRequest)
            .where(CallRequest.status == CallRequestStatus.queued)
            .order_by(priority_expr, CallRequest.created_at.asc())
            .limit(remaining_budget)
            .with_for_update(skip_locked=True)
        ).all()

        if not candidates:
            logger.debug("No QUEUED call requests in this cycle")
            return

        # ------------------------------------------------------------------
        # 3. Resolve voice adapter for the workspace (once per cycle).
        # Falls back to TwilioVoiceAdapter() when no opt-in selection exists.
        # ------------------------------------------------------------------
        adapter = resolve_voice_adapter(
            session,
            workspace_id,
            default_factory=TwilioVoiceAdapter,
        )

        # ------------------------------------------------------------------
        # 4. Dispatch each candidate
        # ------------------------------------------------------------------
        dispatched = 0
        for call_req in candidates:
            try:
                ok = await _initiate_one(session, call_req, workspace_id, adapter)
                if ok:
                    dispatched += 1
            except Exception:
                logger.exception(
                    "Unexpected error processing call_request=%s — aborting batch",
                    call_req.id,
                )
                session.rollback()
                return  # let the next cycle retry

        session.commit()
        logger.debug(
            "Poll cycle complete — dispatched=%d cap=%d/%d",
            dispatched,
            today_count + dispatched,
            daily_cap,
        )


# ---------------------------------------------------------------------------
# APScheduler wiring
# ---------------------------------------------------------------------------


def build_scheduler() -> AsyncIOScheduler:
    """Return a configured (but not yet started) AsyncIOScheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_and_dispatch,
        trigger=IntervalTrigger(seconds=POLL_INTERVAL_SECONDS),
        id="call_worker_poll",
        name="Call Worker — poll & dispatch",
        replace_existing=True,
    )
    return scheduler
