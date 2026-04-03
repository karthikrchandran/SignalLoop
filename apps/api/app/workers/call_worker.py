"""Call scheduling worker — polls for due calls and initiates via Twilio.

Run as: python -m app.workers.call_worker
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain.voice.models import (
    CallOutcome,
    CallRequest,
    CallRequestStatus,
    CallSession,
)
from app.domain_models import Contact
from app.infrastructure.providers.twilio_voice import TwilioVoiceAdapter

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds
DAILY_CALL_CAP = 50
BATCH_SIZE = 5
QUIET_HOURS_START = time(18, 0)  # 6 PM UTC
QUIET_HOURS_END = time(9, 0)  # 9 AM UTC


def _is_quiet_hours() -> bool:
    now = datetime.now(timezone.utc).time()
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return now >= QUIET_HOURS_START or now < QUIET_HOURS_END
    return QUIET_HOURS_START <= now < QUIET_HOURS_END


def _daily_call_count(session: Session) -> int:
    today = datetime.now(timezone.utc).date()
    result = session.exec(
        select(func.count(CallRequest.id)).where(
            func.date(CallRequest.created_at) == today,
            CallRequest.status != CallRequestStatus.failed,
        )
    ).one()
    return result or 0


async def _process_batch() -> int:
    """Process one batch of due call requests."""
    if _is_quiet_hours():
        logger.debug("Quiet hours — skipping calls")
        return 0

    adapter = TwilioVoiceAdapter()
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

        for call_req in due_requests:
            try:
                await _initiate_call(session, adapter, call_req)
                processed += 1
            except Exception:
                logger.exception("Error processing call_request=%s", call_req.id)
                session.rollback()
                break

        session.commit()

    return processed


async def _initiate_call(
    session: Session, adapter: TwilioVoiceAdapter, call_req: CallRequest
) -> None:
    contact = session.get(Contact, call_req.contact_id)
    if not contact:
        logger.warning("Contact %s not found, marking failed", call_req.contact_id)
        call_req.status = CallRequestStatus.failed
        session.add(call_req)
        return

    # Contact needs a phone number — check for one
    phone = getattr(contact, "phone", None) or getattr(contact, "email", "")
    if not phone or "@" in phone:
        logger.warning("No phone for contact %s, marking failed", contact.id)
        call_req.status = CallRequestStatus.failed
        session.add(call_req)
        return

    # Create CallSession
    call_session = CallSession(call_request_id=call_req.id)
    session.add(call_session)
    session.flush()

    # Build callback URLs
    base_url = settings.FRONTEND_HOST.rstrip("/").replace("http://", "https://") or "https://localhost:8000"
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
        call_req.status = CallRequestStatus.in_progress
        logger.info("Call initiated: %s → %s (sid=%s)", contact.email, phone, call_sid)
    else:
        call_req.status = CallRequestStatus.failed
        call_session.outcome = CallOutcome.failed
        logger.warning("Call failed for %s: %s", contact.email, result.get("error"))

    session.add(call_req)
    session.add(call_session)


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Call worker starting (poll=%ds, cap=%d/day)", POLL_INTERVAL, DAILY_CALL_CAP)
    while True:
        try:
            count = await _process_batch()
            if count:
                logger.info("Initiated %d calls", count)
        except Exception:
            logger.exception("Call worker loop error")
        await asyncio.sleep(POLL_INTERVAL)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
