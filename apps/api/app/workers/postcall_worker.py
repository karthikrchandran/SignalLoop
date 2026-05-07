"""Post-call automation worker — sends summary emails after calls complete.

Run as: python -m app.workers.postcall_worker
"""
from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain.voice.models import CallOutcome, CallRequest, CallSession
from app.domain.voice.summary_generator import generate_summary
from app.domain_models import Contact
from app.infrastructure.providers.sendgrid import SendGridAdapter

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds


async def _process_completed_calls() -> int:
    """Find calls with outcomes but no postcall processing, and handle them."""
    processed = 0

    with Session(engine) as session:
        pending_sessions = session.exec(
            select(CallSession)
            .where(
                CallSession.outcome.is_not(None),
                CallSession.postcall_status.is_(None),
            )
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()

        if not pending_sessions:
            return 0

        adapter = SendGridAdapter()

        for call_session in pending_sessions:
            try:
                if call_session.outcome == CallOutcome.answered:
                    await _send_summary(session, adapter, call_session)
                    call_session.postcall_status = "summary_sent"
                else:
                    call_session.postcall_status = "skipped"
                    logger.info(
                        "Skipped summary for call %s (outcome=%s)",
                        call_session.id, call_session.outcome,
                    )
                session.add(call_session)
                processed += 1
            except Exception:
                logger.exception("Postcall error for session=%s", call_session.id)
                call_session.postcall_status = "error"
                session.add(call_session)

        session.commit()

    return processed


async def _send_summary(
    session: Session, adapter: SendGridAdapter, call_session: CallSession
) -> None:
    """Generate and send summary email for an answered call."""
    call_request = session.get(CallRequest, call_session.call_request_id)
    if not call_request:
        return

    contact = session.get(Contact, call_request.contact_id)
    contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip() if contact else "Unknown"
    contact_company = contact.company or "" if contact else ""
    contact_email = contact.email if contact else ""

    summary = generate_summary(
        call_session,
        contact_name=contact_name,
        contact_company=contact_company,
        contact_email=contact_email,
    )

    team_email = settings.TEAM_NOTIFICATION_EMAIL
    if not team_email:
        logger.warning("TEAM_NOTIFICATION_EMAIL not configured, skipping send")
        return

    await adapter.send_email(
        to=team_email,
        subject=summary.subject,
        body_html=summary.html_body,
        body_text=summary.transcript_preview,
    )
    logger.info("Summary email sent for call session %s → %s", call_session.id, team_email)


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Postcall worker starting (poll=%ds)", POLL_INTERVAL)
    while True:
        try:
            count = await _process_completed_calls()
            if count:
                logger.info("Processed %d post-call sessions", count)
        except Exception:
            logger.exception("Postcall worker loop error")
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
