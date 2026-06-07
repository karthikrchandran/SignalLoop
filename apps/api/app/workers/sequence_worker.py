"""Sequence execution worker — polls for due emails and sends via SendGrid.

Run as: python -m app.workers.sequence_worker
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.db import engine
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain_models import (
    Campaign,
    CampaignStatus,
    Contact,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
    PolicyType,
)
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.registry import resolve_email_adapter
from app.infrastructure.providers.sendgrid import SendGridAdapter
from app.workers.heartbeat import record_worker_heartbeat

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60  # seconds
BATCH_SIZE = 50
DEFAULT_DAILY_CAP = 100  # SendGrid free tier
QUIET_HOURS_START = time(21, 0)  # 9 PM UTC
QUIET_HOURS_END = time(8, 0)  # 8 AM UTC
RETRY_DELAYS = [60, 300, 900, 3600, 7200]  # seconds
PENDING_SEND_STALE_AFTER = timedelta(minutes=15)

TOKEN_PATTERN = re.compile(r"\{\{(\w+)\}\}")
ALLOWED_TOKENS = {"first_name", "last_name", "email", "company"}


def _merge_tokens(template: str, contact: Contact) -> str:
    """Replace {{token}} placeholders with contact field values."""
    def replacer(match: re.Match[str]) -> str:
        """Replacer."""
        field = match.group(1)
        if field not in ALLOWED_TOKENS:
            return ""
        value = getattr(contact, field, None)
        return str(value) if value is not None else ""
    return TOKEN_PATTERN.sub(replacer, template)


def _is_quiet_hours() -> bool:
    now = datetime.now(timezone.utc).time()
    if QUIET_HOURS_START > QUIET_HOURS_END:
        # Span midnight: quiet if now >= start OR now < end
        return now >= QUIET_HOURS_START or now < QUIET_HOURS_END
    return QUIET_HOURS_START <= now < QUIET_HOURS_END


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _daily_send_count(
    session: Session,
    *,
    workspace_id: str | None = None,
    campaign_id: uuid.UUID | None = None,
) -> int:
    today = datetime.now(timezone.utc).date()
    statement = select(func.count(SendRequest.id))
    if workspace_id is not None or campaign_id is not None:
        statement = (
            statement
            .join(
                ContactSequenceState,
                SendRequest.contact_sequence_state_id == ContactSequenceState.id,
            )
            .join(EmailSequence, ContactSequenceState.sequence_id == EmailSequence.id)
            .join(Campaign, EmailSequence.campaign_id == Campaign.id)
        )
    statement = statement.where(
        func.date(SendRequest.created_at) == today,
        SendRequest.status != SendRequestStatus.failed,
    )
    if workspace_id is not None:
        statement = statement.where(Campaign.workspace_id == workspace_id)
    if campaign_id is not None:
        statement = statement.where(Campaign.id == campaign_id)
    result = session.exec(statement).one()
    return result or 0


def _is_suppressed(session: Session, email: str) -> bool:
    return session.exec(
        select(EmailSuppression.id).where(EmailSuppression.email == email)
    ).first() is not None


def _campaign_for_state(
    session: Session,
    state: ContactSequenceState,
) -> Campaign | None:
    sequence = session.get(EmailSequence, state.sequence_id)
    if not sequence:
        logger.warning("Sequence %s not found for state=%s", state.sequence_id, state.id)
        return None
    return session.get(Campaign, sequence.campaign_id)


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


def _policy_daily_cap(payload: dict, *, campaign_scope: bool) -> int | None:
    keys = (
        ("campaignDailyCap", "campaignCap", "max_per_day", "maxPerDay", "dailyCap")
        if campaign_scope
        else ("systemDailyCap", "systemCap", "max_per_day", "maxPerDay", "dailyCap")
    )
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid daily cap value for %s: %r", key, value)
    return None


def _effective_daily_cap(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: uuid.UUID | None,
) -> int:
    policies = session.exec(
        select(GovernancePolicy).where(
            GovernancePolicy.workspace_id == workspace_id,
            GovernancePolicy.policy_type == PolicyType.daily_caps,
            GovernancePolicy.status == PolicyStatus.active,
        )
    ).all()

    if campaign_id is not None:
        for policy in policies:
            if policy.campaign_id == campaign_id:
                cap = _policy_daily_cap(policy.payload_json, campaign_scope=True)
                if cap is not None:
                    return cap

    for policy in policies:
        if policy.campaign_id is None:
            cap = _policy_daily_cap(policy.payload_json, campaign_scope=False)
            if cap is not None:
                return cap

    return DEFAULT_DAILY_CAP


def _should_skip_for_governance(
    session: Session,
    state: ContactSequenceState,
) -> bool:
    campaign = _campaign_for_state(session, state)
    if not campaign:
        return False

    if campaign.status == CampaignStatus.paused:
        logger.info("Campaign %s paused - skipping state=%s", campaign.id, state.id)
        return True

    if _is_outreach_paused(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    ):
        logger.info("Control pause active - skipping state=%s", state.id)
        return True

    cap = _effective_daily_cap(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    )
    sent_count = _daily_send_count(
        session,
        workspace_id=campaign.workspace_id,
        campaign_id=campaign.id,
    )
    if sent_count >= cap:
        logger.warning(
            "Daily email cap reached for workspace=%s campaign=%s (%d/%d)",
            campaign.workspace_id,
            campaign.id,
            sent_count,
            cap,
        )
        return True

    return False


async def _process_batch() -> int:
    """Process one batch of due contacts. Returns count processed."""
    if _is_quiet_hours():
        logger.debug("Quiet hours — skipping")
        return 0

    processed = 0

    with Session(engine) as session:
        daily_count = _daily_send_count(session)
        if daily_count >= DEFAULT_DAILY_CAP:
            logger.warning("Daily cap reached (%d/%d)", daily_count, DEFAULT_DAILY_CAP)
            return 0

        remaining_cap = DEFAULT_DAILY_CAP - daily_count

        # SELECT FOR UPDATE SKIP LOCKED prevents double-processing
        due_states = session.exec(
            select(ContactSequenceState)
            .where(
                ContactSequenceState.status == SequenceStatus.active,
                ContactSequenceState.next_send_at <= datetime.now(timezone.utc),
            )
            .order_by(ContactSequenceState.next_send_at)
            .limit(min(BATCH_SIZE, remaining_cap))
            .with_for_update(skip_locked=True)
        ).all()

        if not due_states:
            return 0

        for state in due_states:
            try:
                if _should_skip_for_governance(session, state):
                    continue
                await _process_single(session, state)
                processed += 1
            except Exception:
                logger.exception(
                    "Error processing contact_sequence_state=%s", state.id
                )
                session.rollback()
                break

        session.commit()

    return processed


async def _process_single(
    session: Session,
    state: ContactSequenceState,
) -> None:
    contact = session.get(Contact, state.contact_id)
    if not contact:
        logger.warning("Contact %s not found, stopping sequence", state.contact_id)
        state.status = SequenceStatus.stopped
        session.add(state)
        return

    # Resolve the email adapter for this contact's workspace.  Falls back to
    # SendGridAdapter() when the workspace hasn't opted into a custom
    # provider, which preserves the legacy single-tenant behaviour and lets
    # tests `patch.object(sequence_worker, "SendGridAdapter")` keep working.
    adapter: EmailAdapter = resolve_email_adapter(
        session,
        contact.workspace_id,
        default_factory=SendGridAdapter,
    )

    if _is_suppressed(session, contact.email):
        logger.info("Contact %s is suppressed, stopping sequence", contact.email)
        state.status = SequenceStatus.stopped
        state.signal_type = "suppressed"
        session.add(state)
        return

    # Get the current step
    step = session.exec(
        select(SequenceStep).where(
            SequenceStep.sequence_id == state.sequence_id,
            SequenceStep.step_order == state.current_step,
        )
    ).first()

    if not step:
        # No more steps — sequence complete
        state.status = SequenceStatus.completed
        state.updated_at = datetime.now(timezone.utc)
        session.add(state)
        return

    # Build idempotency key
    idempotency_key = f"{state.contact_id}:{state.sequence_id}:{state.current_step}"

    # Check for existing SendRequest (idempotent)
    existing = session.exec(
        select(SendRequest).where(SendRequest.idempotency_key == idempotency_key)
    ).first()

    if existing and existing.status == SendRequestStatus.sent:
        # Already sent — advance
        _advance_step(session, state, step)
        return

    if existing and existing.status == SendRequestStatus.pending:
        stale_at = _normalize_utc(existing.created_at) + PENDING_SEND_STALE_AFTER
        if _normalize_utc(datetime.now(timezone.utc)) < stale_at:
            logger.info("SendRequest %s already pending; skipping duplicate send", existing.id)
            return

    if existing and existing.status == SendRequestStatus.failed:
        if existing.retry_count >= len(RETRY_DELAYS):
            logger.error(
                "Max retries for %s, marking sequence stopped", idempotency_key
            )
            state.status = SequenceStatus.stopped
            state.signal_type = "send_failed"
            session.add(state)
            return
        # Not yet time for retry
        retry_at = _normalize_utc(existing.created_at) + timedelta(
            seconds=RETRY_DELAYS[existing.retry_count]
        )
        if _normalize_utc(datetime.now(timezone.utc)) < retry_at:
            return

    # Create or reuse SendRequest
    send_request = existing or SendRequest(
        contact_sequence_state_id=state.id,
        step_order=state.current_step,
        idempotency_key=idempotency_key,
    )
    send_request.status = SendRequestStatus.pending
    session.add(send_request)
    session.commit()
    session.refresh(send_request)

    # Merge templates
    subject = _merge_tokens(step.subject_template, contact)
    body_html = _merge_tokens(step.body_template, contact)
    body_text = re.sub(r"<[^>]+>", "", body_html)

    # Send
    result = await adapter.send_email(
        to=contact.email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        idempotency_key=idempotency_key,
        custom_args={"css_id": str(state.id), "step": str(state.current_step)},
    )

    message_id = result.get("message_id", "")
    status_code = result.get("status_code", 0)

    if status_code in (200, 201, 202) and message_id:
        send_request.provider_message_id = message_id
        send_request.status = SendRequestStatus.sent
        send_request.sent_at = datetime.now(timezone.utc)
        session.add(send_request)
        _advance_step(session, state, step)
        session.commit()
        logger.info("Sent email to %s (step %d)", contact.email, state.current_step)
    else:
        send_request.status = SendRequestStatus.failed
        send_request.retry_count += 1
        session.add(send_request)
        session.commit()
        logger.warning(
            "Failed to send to %s (step %d, attempt %d): %s",
            contact.email, state.current_step, send_request.retry_count,
            result.get("error", "unknown"),
        )


def _advance_step(
    session: Session, state: ContactSequenceState, current_step: SequenceStep
) -> None:
    """Advance to next step or complete the sequence."""
    next_step = session.exec(
        select(SequenceStep).where(
            SequenceStep.sequence_id == state.sequence_id,
            SequenceStep.step_order == current_step.step_order + 1,
        )
    ).first()

    now = datetime.now(timezone.utc)
    if next_step:
        state.current_step += 1
        state.next_send_at = now + timedelta(days=next_step.delay_days)
        state.updated_at = now
    else:
        state.status = SequenceStatus.completed
        state.next_send_at = None
        state.updated_at = now
    session.add(state)


async def run_worker() -> None:
    """Main worker loop."""
    logger.info("Sequence worker starting (poll=%ds)", POLL_INTERVAL)
    record_worker_heartbeat(
        "sequence_worker",
        status="starting",
        poll_interval_seconds=POLL_INTERVAL,
    )
    while True:
        try:
            count = await _process_batch()
            record_worker_heartbeat(
                "sequence_worker",
                status="healthy",
                poll_interval_seconds=POLL_INTERVAL,
                processed_count=count,
            )
            if count:
                logger.info("Processed %d contacts", count)
        except Exception as exc:
            record_worker_heartbeat(
                "sequence_worker",
                status="error",
                poll_interval_seconds=POLL_INTERVAL,
                error_message=str(exc),
            )
            logger.exception("Worker loop error")
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
