"""Call scheduling worker — polls for due calls and initiates via Twilio.

Run as: python -m app.workers.call_worker
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain.shared_records import service as shared_record_service

# Timeline cache invalidation moved to route layer (invalidate_timeline_cache via Request object)
# from app.domain.timeline.timeline_service import invalidate_timeline_cache_from_url
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
)
from app.domain_models import (
    Campaign,
    CampaignStatus,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
    PolicyType,
)
from app.infrastructure.providers.base import VoiceAdapter
from app.infrastructure.providers.registry import resolve_voice_adapter
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter
from app.workers.heartbeat import record_worker_heartbeat

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds
DAILY_CALL_CAP = 50
BATCH_SIZE = 5
QUIET_HOURS_START = time(18, 0)  # 6 PM UTC
QUIET_HOURS_END = time(9, 0)  # 9 AM UTC
INITIATING_CALL_STALE_AFTER = timedelta(minutes=15)


def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 4:
        return "****"
    return f"****{digits[-4:]}"


def _is_quiet_hours() -> bool:
    now = datetime.now(timezone.utc).time()
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return now >= QUIET_HOURS_START or now < QUIET_HOURS_END
    return QUIET_HOURS_START <= now < QUIET_HOURS_END


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _daily_call_count(
    session: Session,
    *,
    workspace_id: str | None = None,
    campaign_id: uuid.UUID | None = None,
) -> int:
    today = datetime.now(timezone.utc).date()
    statement = select(func.count(CallRequest.id))
    if workspace_id is not None:
        statement = statement.join(Campaign, CallRequest.campaign_id == Campaign.id)
    statement = statement.where(
        func.date(CallRequest.created_at) == today,
        CallRequest.status != CallRequestStatus.failed,
    )
    if workspace_id is not None:
        statement = statement.where(Campaign.workspace_id == workspace_id)
    if campaign_id is not None:
        statement = statement.where(CallRequest.campaign_id == campaign_id)
    result = session.exec(statement).one()
    return result or 0


def _is_outreach_paused(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: uuid.UUID | None,
) -> bool:
    global_pause = session.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == workspace_id,
            GlobalControlState.campaign_id == None,  # noqa: E711
            GlobalControlState.paused == True,  # noqa: E712
        )
    ).first()
    if global_pause:
        return True

    if campaign_id is None:
        return False

    campaign_pause = session.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == workspace_id,
            GlobalControlState.campaign_id == campaign_id,
            GlobalControlState.paused == True,  # noqa: E712
        )
    ).first()
    return campaign_pause is not None


def _policy_daily_call_cap(payload: dict, *, campaign_scope: bool) -> int | None:
    keys = (
        (
            "campaignDailyCallCap",
            "campaignCallCap",
            "campaignDailyCap",
            "campaignCap",
            "max_calls_per_day",
            "max_per_day",
        )
        if campaign_scope
        else (
            "systemDailyCallCap",
            "systemCallCap",
            "systemDailyCap",
            "systemCap",
            "max_calls_per_day",
            "max_per_day",
        )
    )
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid daily call cap value for %s: %r", key, value)
    return None


def _effective_daily_call_cap(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: uuid.UUID,
) -> int:
    policies = session.exec(
        select(GovernancePolicy).where(
            GovernancePolicy.workspace_id == workspace_id,
            GovernancePolicy.policy_type == PolicyType.daily_caps,
            GovernancePolicy.status == PolicyStatus.active,
        )
    ).all()

    for policy in policies:
        if policy.campaign_id == campaign_id:
            cap = _policy_daily_call_cap(policy.payload_json, campaign_scope=True)
            if cap is not None:
                return cap

    for policy in policies:
        if policy.campaign_id is None:
            cap = _policy_daily_call_cap(policy.payload_json, campaign_scope=False)
            if cap is not None:
                return cap

    return DAILY_CALL_CAP


def _should_skip_for_governance(session: Session, call_req: CallRequest) -> bool:
    campaign = session.get(Campaign, call_req.campaign_id)
    if not campaign:
        return False

    if campaign.status == CampaignStatus.paused:
        logger.info("Campaign %s paused - skipping call_request=%s", campaign.id, call_req.id)
        return True

    if _is_outreach_paused(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    ):
        logger.info("Control pause active - skipping call_request=%s", call_req.id)
        return True

    cap = _effective_daily_call_cap(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    )
    call_count = _daily_call_count(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    )
    if call_count >= cap:
        logger.warning(
            "Daily call cap reached for workspace=%s campaign=%s (%d/%d)",
            campaign.workspace_id,
            campaign.id,
            call_count,
            cap,
        )
        return True

    return False


async def _process_batch() -> int:
    """Process one batch of due call requests."""
    if _is_quiet_hours():
        logger.debug("Quiet hours — skipping calls")
        return 0

    processed = 0

    with Session(engine) as session:
        daily_count = _daily_call_count(session)
        if daily_count >= DAILY_CALL_CAP:
            logger.warning("Daily call cap reached (%d/%d)", daily_count, DAILY_CALL_CAP)
            return 0

        remaining = DAILY_CALL_CAP - daily_count

        due_requests = session.exec(
            select(CallRequest)
            .where(
                CallRequest.status == CallRequestStatus.queued,
                CallRequest.scheduled_at <= datetime.now(timezone.utc),
            )
            .order_by(CallRequest.scheduled_at)
            .limit(min(BATCH_SIZE, remaining))
            .with_for_update(skip_locked=True)
        ).all()

        if not due_requests:
            return 0

        timeline_cache_targets: set[tuple[uuid.UUID, uuid.UUID]] = set()
        for call_req in due_requests:
            try:
                if _should_skip_for_governance(session, call_req):
                    continue
                if target := await _initiate_call(session, call_req):
                    timeline_cache_targets.add(target)
                processed += 1
            except Exception:
                logger.exception("Error processing call_request=%s", call_req.id)
                session.rollback()
                break

        session.commit()
        # Timeline cache invalidation (per-contact) is handled by workers/call_worker side effects,
        # but the call_worker process cannot invalidate caches directly (no Request object).
        # Caches will auto-expire or be invalidated by route handlers.
        # for contact_id, campaign_id in timeline_cache_targets:
        #     await invalidate_timeline_cache_from_url(settings.REDIS_URL, contact_id, campaign_id)

    return processed


async def _initiate_call(
    session: Session, call_req: CallRequest
) -> tuple[uuid.UUID, uuid.UUID] | None:
    campaign = session.get(Campaign, call_req.campaign_id)
    workspace_id = campaign.workspace_id if campaign else settings.DEFAULT_WORKSPACE_ID
    shared_contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=call_req.shared_contact_id,
    )
    contact = (
        shared_record_service.shared_contact_to_contact(shared_contact)
        if shared_contact
        else None
    )
    if not contact:
        logger.warning(
            "Shared contact %s not found, marking failed",
            call_req.shared_contact_id,
        )
        call_req.status = CallRequestStatus.failed
        session.add(call_req)
        return None

    # Resolve the voice adapter for this contact's workspace.  Falls back to
    # TwilioVoiceAdapter() when no explicit selection exists so that legacy
    # tests `patch.object(call_worker, "TwilioVoiceAdapter")` keep working.
    adapter: VoiceAdapter = resolve_voice_adapter(
        session,
        contact.workspace_id,
        default_factory=TwilioVoiceAdapter,
    )

    # Contact needs a phone number — check for one
    phone = getattr(contact, "phone", None) or getattr(contact, "email", "")
    if not phone or "@" in phone:
        logger.warning("No phone for contact %s, marking failed", contact.id)
        call_req.status = CallRequestStatus.failed
        session.add(call_req)
        return None

    call_session = session.exec(
        select(CallSession)
        .where(CallSession.call_request_id == call_req.id)
        .with_for_update()
    ).first()
    if call_session and call_session.twilio_call_sid:
        call_req.status = CallRequestStatus.in_progress
        session.add(call_req)
        return None

    if call_session and call_session.twilio_status == "initiating":
        updated_at = call_session.twilio_status_updated_at or call_session.created_at
        stale_at = _normalize_utc(updated_at) + INITIATING_CALL_STALE_AFTER
        if datetime.now(timezone.utc) >= stale_at:
            logger.warning(
                "CallSession %s is stale initiating; skipping automatic redial because provider outcome is unknown",
                call_session.id,
            )
        else:
            logger.info("CallSession %s already initiating; skipping duplicate dial", call_session.id)
        call_req.status = CallRequestStatus.in_progress
        session.add(call_req)
        return None

    account_sid = getattr(adapter, "_account_sid", "") or None
    if call_session is None:
        call_session = CallSession(
            call_request_id=call_req.id,
            twilio_account_sid=account_sid,
        )
        session.add(call_session)
        session.flush()
    else:
        call_session.twilio_account_sid = account_sid or call_session.twilio_account_sid
    call_session.twilio_status = "initiating"
    call_session.twilio_status_updated_at = datetime.now(timezone.utc)
    session.add(call_session)
    session.commit()
    session.refresh(call_session)

    # Build callback URLs
    base_url = f"https://{settings.SERVER_HOST.rstrip('/')}"
    api_base = f"{base_url}{settings.API_V1_STR}"
    twiml_url = f"{api_base}/voice/twiml"
    status_url = f"{api_base}/voice/status"

    result = await adapter.initiate_call(
        to=phone,
        twiml_url=twiml_url,
        status_callback_url=status_url,
    )

    call_sid = result.get("call_sid", "")
    if call_sid:
        call_session.twilio_call_sid = call_sid
        call_session.twilio_account_sid = account_sid or call_session.twilio_account_sid
        call_session.twilio_status = "initiated"
        call_session.twilio_status_updated_at = datetime.now(timezone.utc)
        call_req.status = CallRequestStatus.in_progress
        session.add(call_req)
        session.add(call_session)
        session.commit()
        logger.info("Call initiated: contact=%s phone=%s sid=%s", contact.id, _mask_phone(phone), call_sid)
    else:
        call_req.status = CallRequestStatus.failed
        call_session.outcome = CallOutcome.failed
        call_session.twilio_status = "failed"
        call_session.twilio_status_updated_at = datetime.now(timezone.utc)
        session.add(call_req)
        session.add(call_session)
        session.commit()
        error_detail = result.get("error_code") or result.get("error", "twilio_rejected")
        logger.warning("Call failed for contact=%s: %s", contact.id, error_detail)

    return call_req.shared_contact_id, call_req.campaign_id


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Call worker starting (poll=%ds, cap=%d/day)", POLL_INTERVAL, DAILY_CALL_CAP)
    record_worker_heartbeat(
        "call_worker",
        status="starting",
        poll_interval_seconds=POLL_INTERVAL,
    )
    while True:
        try:
            count = await _process_batch()
            record_worker_heartbeat(
                "call_worker",
                status="healthy",
                poll_interval_seconds=POLL_INTERVAL,
                processed_count=count,
            )
            if count:
                logger.info("Initiated %d calls", count)
        except Exception as exc:
            record_worker_heartbeat(
                "call_worker",
                status="error",
                poll_interval_seconds=POLL_INTERVAL,
                error_message=str(exc),
            )
            logger.exception("Call worker loop error")
        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
