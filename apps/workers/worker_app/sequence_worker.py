"""Standalone sequence-execution worker for SignalLoop.

Polls ``contact_sequence_state`` every 60 s for rows that are ACTIVE and
past their ``next_send_at`` timestamp, then merges templates, calls SendGrid,
advances the step pointer, and writes an audit trail.

This module is a UV-workspace member and can import from the ``app`` package
(apps/api) because both are installed into the shared .venv.  A sys.path
bootstrap at the bottom of the file provides a local-dev fallback.
"""
from __future__ import annotations

import logging
import re
import sys
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---------------------------------------------------------------------------
# sys.path bootstrap — allows running the file directly from the repo root
# even when ``app`` (apps/api) is not yet installed as an editable package.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

# ---------------------------------------------------------------------------
# Third-party / API-app imports (available after path bootstrap above)
# ---------------------------------------------------------------------------
from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.audit.audit_events import AuditEvent  # noqa: E402
from app.domain.sequences.models import (  # noqa: E402
    ContactSequenceState,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
    SequenceStep,
)
from app.domain.sequences.suppression import is_email_suppressed  # noqa: E402
from app.domain.policies.consent_sync_service import is_contact_actionable  # noqa: E402
from app.domain_models import (  # noqa: E402
    Campaign,
    Contact,
    GlobalControlState,
    GovernancePolicy,
    PolicyStatus,
    PolicyType,
)
from app.infrastructure.providers.base import EmailAdapter  # noqa: E402
from app.infrastructure.providers.registry import resolve_email_adapter  # noqa: E402
from app.infrastructure.providers.sendgrid import SendGridAdapter  # noqa: E402

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS: int = 60
BATCH_SIZE: int = 50
DEFAULT_DAILY_CAP: int = 200
MAX_RETRIES: int = 5

# Quiet hours: do NOT send before 6 AM or from 9 PM onward (local to contact)
_SEND_WINDOW_START = time(6, 0)   # 06:00 — earliest allowed send
_SEND_WINDOW_END = time(21, 0)    # 21:00 — latest allowed send (exclusive)

# Tokens that may appear in subject/body templates
_TOKEN_PATTERN = re.compile(r"\{\{(\w+)\}\}")
_ALLOWED_TOKENS: frozenset[str] = frozenset(
    {"first_name", "last_name", "email", "company", "phone"}
)

# ---------------------------------------------------------------------------
# Template merging
# ---------------------------------------------------------------------------


def _merge_tokens(template: str, contact: Contact) -> str:
    """Replace ``{{token}}`` placeholders with contact field values."""

    def _replace(m: re.Match[str]) -> str:
        field = m.group(1)
        if field not in _ALLOWED_TOKENS:
            return ""
        value = getattr(contact, field, None)
        return str(value) if value is not None else ""

    return _TOKEN_PATTERN.sub(_replace, template)


# ---------------------------------------------------------------------------
# Quiet-hours guard
# ---------------------------------------------------------------------------


def _in_quiet_hours(contact: Contact) -> bool:
    """Return *True* if the contact's local time is outside the send window."""
    try:
        tz = ZoneInfo(contact.timezone or "UTC")
    except (ZoneInfoNotFoundError, Exception):
        tz = ZoneInfo("UTC")

    now_local = datetime.now(tz).time()
    return not (_SEND_WINDOW_START <= now_local < _SEND_WINDOW_END)


# ---------------------------------------------------------------------------
# Governance helpers
# ---------------------------------------------------------------------------


def _get_daily_cap(
    session: Session,
    workspace_id: str,
    campaign_id: uuid.UUID,
) -> int:
    """Return the effective daily-email cap for *workspace_id* / *campaign_id*."""
    policies = session.exec(
        select(GovernancePolicy).where(
            GovernancePolicy.workspace_id == workspace_id,
            GovernancePolicy.policy_type == PolicyType.daily_caps,
            GovernancePolicy.status == PolicyStatus.active,
        )
    ).all()

    # Campaign-specific policy takes precedence over workspace-wide.
    for p in policies:
        if p.campaign_id == campaign_id:
            return int(p.payload_json.get("max_per_day", DEFAULT_DAILY_CAP))
    for p in policies:
        if p.campaign_id is None:
            return int(p.payload_json.get("max_per_day", DEFAULT_DAILY_CAP))
    return DEFAULT_DAILY_CAP


def _daily_workspace_send_count(session: Session, workspace_id: str) -> int:
    """Count non-failed sends today across all sequences in *workspace_id*."""
    today = datetime.now(UTC).date()
    result = session.exec(
        select(func.count(SendRequest.id))
        .join(
            ContactSequenceState,
            SendRequest.contact_sequence_state_id == ContactSequenceState.id,
        )
        .join(EmailSequence, ContactSequenceState.sequence_id == EmailSequence.id)
        .join(Campaign, EmailSequence.campaign_id == Campaign.id)
        .where(
            Campaign.workspace_id == workspace_id,
            func.date(SendRequest.created_at) == today,
            SendRequest.status != SendRequestStatus.failed,
        )
    ).one()
    return result or 0


def _workspace_is_globally_paused(session: Session, workspace_id: str) -> bool:
    row = session.exec(
        select(GlobalControlState).where(
            GlobalControlState.workspace_id == workspace_id,
            GlobalControlState.campaign_id == None,  # noqa: E711 — workspace-level
            GlobalControlState.paused == True,  # noqa: E712
        )
    ).first()
    return row is not None


# ---------------------------------------------------------------------------
# Audit helper (writes into the *current* session — committed with the state)
# ---------------------------------------------------------------------------


def _write_audit(
    session: Session,
    *,
    event_name: str,
    workspace_id: str,
    state: ContactSequenceState,
    send_request_id: uuid.UUID | None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "contact_sequence_state_id": str(state.id),
        "contact_id": str(state.contact_id),
        "sequence_id": str(state.sequence_id),
        "step_order": state.current_step,
    }
    if send_request_id is not None:
        payload["send_request_id"] = str(send_request_id)
    if extra:
        payload.update(extra)

    session.add(
        AuditEvent(
            event_name=event_name,
            workspace_id=workspace_id,
            resource_type="send_request",
            resource_id=str(send_request_id) if send_request_id else str(state.id),
            payload=payload,
        )
    )


# ---------------------------------------------------------------------------
# Single-contact processing
# ---------------------------------------------------------------------------


async def _process_single(
    session: Session,
    state: ContactSequenceState,
    workspace_id: str,
    campaign_id: uuid.UUID,
    adapter: EmailAdapter | None = None,
) -> None:
    """Process one due ``ContactSequenceState`` row.

    All DB writes happen on *session*; caller commits/rolls back.
    """
    sequence = session.get(EmailSequence, state.sequence_id)
    campaign = session.get(Campaign, campaign_id)
    if (
        sequence is None
        or campaign is None
        or sequence.campaign_id != campaign.id
        or campaign.workspace_id != workspace_id
    ):
        state.status = SequenceStatus.stopped
        state.signal_type = "campaign_workspace_mismatch"
        session.add(state)
        return

    # -- Contact lookup -------------------------------------------------------
    contact = session.get(Contact, state.contact_id)
    if contact is None:
        logger.warning("Contact %s not found — stopping sequence %s", state.contact_id, state.id)
        state.status = SequenceStatus.stopped
        state.signal_type = "contact_not_found"
        state.updated_at = datetime.now(UTC)
        session.add(state)
        return

    if contact.workspace_id != workspace_id:
        state.status = SequenceStatus.stopped
        state.signal_type = "workspace_mismatch"
        state.updated_at = datetime.now(UTC)
        session.add(state)
        return

    actionable, reason = is_contact_actionable(contact.model_dump(), "email")
    if not actionable:
        state.status = SequenceStatus.stopped
        state.signal_type = reason
        state.updated_at = datetime.now(UTC)
        session.add(state)
        return

    # -- Suppression check ----------------------------------------------------
    if is_email_suppressed(session, workspace_id, contact.email):
        logger.info("Contact %s suppressed — stopping sequence %s", contact.email, state.id)
        state.status = SequenceStatus.stopped
        state.signal_type = "suppressed"
        state.updated_at = datetime.now(UTC)
        session.add(state)
        return

    # -- Quiet-hours check ----------------------------------------------------
    if _in_quiet_hours(contact):
        logger.debug(
            "Quiet hours for contact %s (tz=%s) — deferring", contact.email, contact.timezone
        )
        return  # will be retried on the next poll

    # -- Sequence step --------------------------------------------------------
    step = session.exec(
        select(SequenceStep).where(
            SequenceStep.sequence_id == state.sequence_id,
            SequenceStep.step_order == state.current_step,
        )
    ).first()

    if step is None:
        # No more steps — sequence complete
        state.status = SequenceStatus.completed
        state.next_send_at = None
        state.updated_at = datetime.now(UTC)
        session.add(state)
        return

    # -- Idempotency key (task spec: "{contact_sequence_state_id}:{current_step}") --
    idempotency_key = f"{state.id}:{state.current_step}"

    # -- Exactly-once guard ---------------------------------------------------
    existing: SendRequest | None = session.exec(
        select(SendRequest).where(
            SendRequest.workspace_id == workspace_id,
            SendRequest.idempotency_key == idempotency_key,
        )
    ).first()

    if existing and existing.status == SendRequestStatus.sent:
        # Already delivered — just advance the pointer
        _advance_step(session, state, step)
        return

    if existing and existing.status == SendRequestStatus.pending:
        logger.warning(
            "SendRequest %s is pending; skipping automatic resend because provider outcome is unknown",
            existing.id,
        )
        return

    # -- Max-retries guard ----------------------------------------------------
    if existing and existing.retry_count >= MAX_RETRIES:
        logger.error(
            "Max retries (%d) reached for %s — marking FAILED", MAX_RETRIES, idempotency_key
        )
        existing.status = SendRequestStatus.failed
        session.add(existing)
        state.status = SequenceStatus.stopped
        state.signal_type = "send_failed"
        state.updated_at = datetime.now(UTC)
        session.add(state)
        _write_audit(
            session,
            event_name="sequence.email.max_retries_exceeded",
            workspace_id=workspace_id,
            state=state,
            send_request_id=existing.id,
            extra={"retry_count": existing.retry_count},
        )
        return

    # -- Create or reuse SendRequest ------------------------------------------
    send_request: SendRequest = existing or SendRequest(
        workspace_id=workspace_id,
        contact_sequence_state_id=state.id,
        step_order=state.current_step,
        idempotency_key=idempotency_key,
    )

    # -- Template rendering ---------------------------------------------------
    subject = _merge_tokens(step.subject_template, contact)
    body_html = _merge_tokens(step.body_template, contact)
    body_text = re.sub(r"<[^>]+>", "", body_html)

    # -- Send -----------------------------------------------------------------
    if adapter is None:
        adapter = resolve_email_adapter(
            session,
            workspace_id,
            default_factory=SendGridAdapter,
        )
    result = await adapter.send_email(
        to=contact.email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        idempotency_key=idempotency_key,
        custom_args={
            "workspace_id": workspace_id,
            "css_id": str(state.id),
            "step": str(state.current_step),
        },
    )

    status_code: int = result.get("status_code", 0)
    message_id: str = result.get("message_id", "")
    success = status_code in (200, 201, 202) and bool(message_id)

    if success:
        send_request.provider_message_id = message_id
        send_request.status = SendRequestStatus.sent
        send_request.sent_at = datetime.now(UTC)
        session.add(send_request)
        _advance_step(session, state, step)
        _write_audit(
            session,
            event_name="sequence.email.sent",
            workspace_id=workspace_id,
            state=state,
            send_request_id=send_request.id,
            extra={"status_code": status_code, "message_id": message_id},
        )
        logger.info(
            "Sent email to %s (state=%s step=%d msg=%s)",
            contact.email, state.id, state.current_step, message_id,
        )
    else:
        send_request.status = SendRequestStatus.failed
        send_request.retry_count = (send_request.retry_count or 0) + 1
        session.add(send_request)
        _write_audit(
            session,
            event_name="sequence.email.failed",
            workspace_id=workspace_id,
            state=state,
            send_request_id=send_request.id,
            extra={
                "status_code": status_code,
                "error": result.get("error", ""),
                "retry_count": send_request.retry_count,
            },
        )
        logger.warning(
            "Send failed for %s (state=%s step=%d attempt=%d): %s",
            contact.email, state.id, state.current_step,
            send_request.retry_count, result.get("error", ""),
        )


# ---------------------------------------------------------------------------
# Step advancement
# ---------------------------------------------------------------------------


def _advance_step(
    session: Session,
    state: ContactSequenceState,
    current_step: SequenceStep,
) -> None:
    """Move to the next step or mark the sequence completed."""
    next_step = session.exec(
        select(SequenceStep).where(
            SequenceStep.sequence_id == state.sequence_id,
            SequenceStep.step_order == current_step.step_order + 1,
        )
    ).first()

    now = datetime.now(UTC)
    if next_step:
        state.current_step = next_step.step_order
        state.next_send_at = now + timedelta(days=next_step.delay_days)
        state.updated_at = now
    else:
        state.status = SequenceStatus.completed
        state.next_send_at = None
        state.updated_at = now

    session.add(state)


# ---------------------------------------------------------------------------
# Batch processor
# ---------------------------------------------------------------------------


async def process_batch() -> int:
    """Query one batch of due contacts and send emails.

    Returns the number of contacts successfully processed.
    """
    processed = 0
    now = datetime.now(UTC)

    with Session(engine) as session:
        workspace_ids = session.exec(
            select(Campaign.workspace_id)
            .join(EmailSequence, EmailSequence.campaign_id == Campaign.id)
            .join(ContactSequenceState, ContactSequenceState.sequence_id == EmailSequence.id)
            .where(
                ContactSequenceState.status == SequenceStatus.active,
                ContactSequenceState.next_send_at <= now,
            )
            .distinct()
            .order_by(Campaign.workspace_id)
        ).all()
        due_states: list[ContactSequenceState] = []
        for due_workspace_id in workspace_ids:
            due_states.extend(
                session.exec(
                    select(ContactSequenceState)
                    .join(
                        EmailSequence,
                        ContactSequenceState.sequence_id == EmailSequence.id,
                    )
                    .join(Campaign, EmailSequence.campaign_id == Campaign.id)
                    .where(
                        Campaign.workspace_id == due_workspace_id,
                        ContactSequenceState.status == SequenceStatus.active,
                        ContactSequenceState.next_send_at <= now,
                    )
                    .order_by(ContactSequenceState.next_send_at)
                    .limit(BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                ).all()
            )

        if not due_states:
            return 0

        # Cache workspace info to avoid repeated JOINs and per-workspace cap checks.
        _cap_cache: dict[str, int] = {}       # workspace_id → effective daily cap
        _count_cache: dict[str, int] = {}     # workspace_id → sends so far today
        _adapter_cache: dict[str, EmailAdapter] = {}  # workspace_id → adapter

        for state in due_states:
            # -- Resolve workspace / campaign ---------------------------------
            seq = session.get(EmailSequence, state.sequence_id)
            if seq is None:
                logger.warning("EmailSequence %s missing for state %s", state.sequence_id, state.id)
                continue
            campaign = session.get(Campaign, seq.campaign_id)
            if campaign is None:
                logger.warning("Campaign %s missing for state %s", seq.campaign_id, state.id)
                continue

            workspace_id = campaign.workspace_id
            campaign_id = campaign.id

            # -- Global-pause check -------------------------------------------
            if _workspace_is_globally_paused(session, workspace_id):
                logger.debug("Workspace %s globally paused — skipping batch", workspace_id)
                continue

            # -- Daily-cap check (load once per workspace per batch) ----------
            if workspace_id not in _cap_cache:
                _cap_cache[workspace_id] = _get_daily_cap(session, workspace_id, campaign_id)
                _count_cache[workspace_id] = _daily_workspace_send_count(session, workspace_id)

            cap = _cap_cache[workspace_id]
            if _count_cache[workspace_id] >= cap:
                logger.warning(
                    "Daily cap reached for workspace %s (%d/%d)",
                    workspace_id, _count_cache[workspace_id], cap,
                )
                continue  # skip remaining contacts for this workspace

            contact = session.get(Contact, state.contact_id)
            if contact is None or contact.workspace_id != workspace_id:
                state.status = SequenceStatus.stopped
                state.signal_type = "workspace_mismatch"
                session.add(state)
                continue
            actionable, reason = is_contact_actionable(contact.model_dump(), "email")
            if not actionable:
                state.status = SequenceStatus.stopped
                state.signal_type = reason
                session.add(state)
                continue

            # -- Build (or reuse) email adapter (per-workspace registry) ----
            if workspace_id not in _adapter_cache:
                # Falls back to SendGridAdapter() when the workspace hasn't
                # opted into a custom provider — preserves legacy behaviour
                # and keeps `patch.object(sequence_worker, "SendGridAdapter")`
                # working in tests.
                _adapter_cache[workspace_id] = resolve_email_adapter(
                    session,
                    workspace_id,
                    default_factory=SendGridAdapter,
                )

            adapter = _adapter_cache[workspace_id]

            # -- Per-contact processing with savepoint isolation ---------------
            try:
                sp = session.begin_nested()
                await _process_single(session, state, workspace_id, campaign_id, adapter)
                sp.commit()
                processed += 1
                # Optimistically increment in-memory counter to respect cap
                _count_cache[workspace_id] = _count_cache.get(workspace_id, 0) + 1
            except Exception:
                sp.rollback()
                logger.exception("Unhandled error processing state %s", state.id)

        session.commit()

    return processed
