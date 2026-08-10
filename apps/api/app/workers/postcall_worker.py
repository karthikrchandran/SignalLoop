"""Post-call automation worker — sends summary emails after calls complete.

Run as: python -m app.workers.postcall_worker
"""
from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session, select

from app.core.db import engine
from app.domain.outreach.outbox_service import (
    enqueue_outbox_event,
    mark_outbox_published,
)
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain.shared_records import service as shared_record_service
from app.domain.voice.models import CallOutcome, CallRequest, CallSession
from app.domain.voice.summary_generator import generate_summary
from app.domain_models import Campaign, OutboxEvent
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.registry import resolve_email_adapter
from app.infrastructure.providers.sendgrid import SendGridAdapter
from app.workers.heartbeat import record_worker_heartbeat

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds


def _postcall_summary_intent_key(call_session_id: object) -> str:
    return f"postcall:{call_session_id}:summary_email"


def _prepare_postcall_summary_intent(
    session: Session,
    *,
    call_session: CallSession,
    call_request: CallRequest,
    team_email: str,
) -> OutboxEvent | None:
    intent_key = _postcall_summary_intent_key(call_session.id)
    existing = session.exec(
        select(OutboxEvent).where(
            OutboxEvent.workspace_id == call_request.workspace_id,
            OutboxEvent.idempotency_key == intent_key,
        )
    ).first()
    if existing is not None:
        if existing.published_at is None:
            raise RuntimeError(
                f"Post-call summary for call session {call_session.id} is already in progress"
            )
        logger.info(
            "Skipping duplicate post-call summary for call session %s",
            call_session.id,
        )
        return None

    return enqueue_outbox_event(
        session,
        workspace_id=call_request.workspace_id,
        aggregate_id=call_session.id,
        aggregate_type="call_session",
        event_type="postcall.summary_email_requested",
        event_data={
            "workspace_id": call_request.workspace_id,
            "call_session_id": str(call_session.id),
            "call_request_id": str(call_request.id),
            "contact_id": str(call_request.shared_contact_id),
            "campaign_id": str(call_request.campaign_id),
            "to": team_email,
        },
        idempotency_key=intent_key,
    )


def _provider_send_accepted(result: dict[str, object]) -> bool:
    status_code = int(str(result.get("status_code") or 0))
    return 200 <= status_code < 300


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

        for call_session in pending_sessions:
            try:
                if call_session.outcome == CallOutcome.answered:
                    await _send_summary(session, call_session)
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
    session: Session, call_session: CallSession
) -> None:
    """Generate and send summary email for an answered call."""
    call_request = session.get(CallRequest, call_session.call_request_id)
    if not call_request:
        raise RuntimeError("post-call CallRequest missing")

    workspace_id = call_request.workspace_id
    campaign = session.get(Campaign, call_request.campaign_id)
    if campaign is None:
        raise RuntimeError("post-call campaign missing")
    if campaign.workspace_id != workspace_id:
        raise RuntimeError("post-call campaign workspace mismatch")
    shared_contact = shared_record_service.get_shared_contact(
        workspace_id=workspace_id,
        contact_id=call_request.shared_contact_id,
    )
    contact = (
        shared_record_service.shared_contact_to_contact(shared_contact)
        if shared_contact
        else None
    )
    if contact is None:
        raise RuntimeError("post-call contact missing")
    if contact.workspace_id != workspace_id:
        raise RuntimeError("post-call contact workspace mismatch")
    contact_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
    contact_company = contact.company or ""
    contact_email = contact.email

    summary = generate_summary(
        call_session,
        contact_name=contact_name,
        contact_company=contact_company,
        contact_email=contact_email,
    )

    team_email = resolve_team_notification_email(session, workspace_id)
    if not team_email:
        logger.warning("TEAM_NOTIFICATION_EMAIL not configured, skipping send")
        return

    intent = _prepare_postcall_summary_intent(
        session,
        call_session=call_session,
        call_request=call_request,
        team_email=team_email,
    )
    if intent is None:
        return

    # Resolve adapter for this workspace; falls back to SendGridAdapter() so
    # tests can still `patch('app.workers.postcall_worker.SendGridAdapter')`.
    adapter: EmailAdapter = resolve_email_adapter(
        session,
        workspace_id,
        default_factory=SendGridAdapter,
    )

    result = await adapter.send_email(
        to=team_email,
        subject=summary.subject,
        body_html=summary.html_body,
        body_text=summary.transcript_preview,
        idempotency_key=intent.idempotency_key,
    )
    if not _provider_send_accepted(result):
        raise RuntimeError(
            f"Post-call summary provider rejected send for call session {call_session.id}"
        )
    mark_outbox_published(
        session, workspace_id=call_request.workspace_id, event_id=intent.id
    )
    logger.info("Summary email sent for call session %s → %s", call_session.id, team_email)


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Postcall worker starting (poll=%ds)", POLL_INTERVAL)
    record_worker_heartbeat(
        "postcall_worker",
        status="starting",
        poll_interval_seconds=POLL_INTERVAL,
    )
    while True:
        try:
            count = await _process_completed_calls()
            record_worker_heartbeat(
                "postcall_worker",
                status="healthy",
                poll_interval_seconds=POLL_INTERVAL,
                processed_count=count,
            )
            if count:
                logger.info("Processed %d post-call sessions", count)
        except Exception as exc:
            record_worker_heartbeat(
                "postcall_worker",
                status="error",
                poll_interval_seconds=POLL_INTERVAL,
                error_message=str(exc),
            )
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
