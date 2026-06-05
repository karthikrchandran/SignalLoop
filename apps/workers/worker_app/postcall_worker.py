"""Post-call automation worker.

Polls CallSession rows where the parent CallRequest is COMPLETED and
post_call_processed is False, then for each session:

1. Builds a structured call summary dict.
2. Renders plaintext + HTML email (f-string templates, no Jinja).
3. Sends the summary to the workspace team notification address via SendGrid.
4. If scheduling_interest is True, sets postcall_status='scheduling_pending'
   on the CallSession for manual follow-up.
5. Marks CallSession.post_call_processed = True.
6. Writes an AuditEvent row.

This module is driven by APScheduler every 60 seconds (see main.py).
"""
from __future__ import annotations

import html as _html
import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.domain.audit.audit_events import AuditEvent
from app.domain.providers.credential_resolver import resolve_provider_credentials
from app.domain.voice.models import CallOutcome, CallRequest, CallRequestStatus, CallSession
from app.domain_models import Campaign, Contact, NotificationProvider
from app.infrastructure.providers.sendgrid import SendGridAdapter
from app.infrastructure.providers.registry import resolve_email_adapter

logger = logging.getLogger(__name__)

BATCH_SIZE = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _outcome_label(outcome: CallOutcome | None) -> str:
    _map: dict[CallOutcome, str] = {
        CallOutcome.answered: "ANSWERED",
        CallOutcome.voicemail: "VOICEMAIL",
        CallOutcome.no_answer: "NO_ANSWER",
        CallOutcome.busy: "BUSY",
        CallOutcome.failed: "FAILED",
    }
    return _map.get(outcome, "UNKNOWN") if outcome else "UNKNOWN"


def _coerce_unanswered(raw: Any) -> list[str]:
    """Normalise unanswered_questions to a plain list of strings regardless
    of whether it was stored as a JSON array or object."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(v) for v in raw]
    if isinstance(raw, dict):
        return [str(v) for v in raw.values()]
    return [str(raw)]


def _build_summary(
    req: CallRequest,
    sess: CallSession,
    contact: Contact | None,
    campaign: Campaign | None,
) -> dict[str, Any]:
    first = (contact.first_name or "") if contact else ""
    last = (contact.last_name or "") if contact else ""
    contact_name = f"{first} {last}".strip() or "Unknown"

    return {
        "contact_name": contact_name,
        "phone": (contact.phone if contact else None) or "N/A",
        "campaign_name": campaign.name if campaign else str(req.campaign_id),
        "campaign_id": str(req.campaign_id),
        "workspace_id": campaign.workspace_id if campaign else settings.DEFAULT_WORKSPACE_ID,
        "call_duration_seconds": sess.duration_seconds,
        "outcome": _outcome_label(sess.outcome),
        "transcript": sess.transcript or "",
        "unanswered_questions": _coerce_unanswered(sess.unanswered_questions),
        "scheduling_intent": sess.scheduling_interest,
    }


def _render_email(summary: dict[str, Any]) -> tuple[str, str]:
    """Return (body_text, body_html).  HTML user values are escaped."""
    outcome = summary["outcome"]
    contact_name = summary["contact_name"]
    phone = summary["phone"]
    campaign = summary["campaign_name"]
    duration = summary["call_duration_seconds"]
    transcript = summary["transcript"] or "(no transcript)"
    unanswered: list[str] = summary["unanswered_questions"]
    scheduling_note = "YES — schedule follow-up" if summary["scheduling_intent"] else "No"

    # ---- plain text --------------------------------------------------------
    unanswered_text = (
        "\n".join(f"  - {q}" for q in unanswered) if unanswered else "  (none)"
    )
    body_text = (
        f"Post-Call Summary\n"
        f"=================\n"
        f"Contact:           {contact_name}\n"
        f"Phone:             {phone}\n"
        f"Campaign:          {campaign}\n"
        f"Outcome:           {outcome}\n"
        f"Duration:          {duration}s\n"
        f"Scheduling intent: {scheduling_note}\n"
        f"\nTranscript:\n{transcript}\n"
        f"\nUnanswered questions:\n{unanswered_text}\n"
    )

    # ---- HTML (escape all user-controlled values) --------------------------
    def e(v: str) -> str:  # noqa: E741
        return _html.escape(str(v))

    unanswered_html = (
        "".join(f"<li>{e(q)}</li>" for q in unanswered)
        if unanswered
        else "<li>(none)</li>"
    )
    body_html = (
        "<h2>Post-Call Summary</h2>"
        "<table><tbody>"
        f"<tr><th>Contact</th><td>{e(contact_name)}</td></tr>"
        f"<tr><th>Phone</th><td>{e(phone)}</td></tr>"
        f"<tr><th>Campaign</th><td>{e(campaign)}</td></tr>"
        f"<tr><th>Outcome</th><td>{e(outcome)}</td></tr>"
        f"<tr><th>Duration</th><td>{e(str(duration))}s</td></tr>"
        f"<tr><th>Scheduling intent</th><td>{e(scheduling_note)}</td></tr>"
        "</tbody></table>"
        f"<h3>Transcript</h3><pre>{e(transcript)}</pre>"
        f"<h3>Unanswered questions</h3><ul>{unanswered_html}</ul>"
    )
    return body_text, body_html


# ---------------------------------------------------------------------------
# Per-session processing
# ---------------------------------------------------------------------------

async def _process_session(
    db: Session,
    req: CallRequest,
    sess: CallSession,
) -> None:
    contact = db.get(Contact, req.contact_id)
    campaign = db.get(Campaign, req.campaign_id)
    workspace_id: str = (
        campaign.workspace_id if campaign else settings.DEFAULT_WORKSPACE_ID
    )

    summary = _build_summary(req, sess, contact, campaign)
    body_text, body_html = _render_email(summary)
    subject = (
        f"[EngageHub] Post-call: {summary['contact_name']} — {summary['outcome']}"
    )

    email_sent = False
    to_email = settings.TEAM_NOTIFICATION_EMAIL
    if to_email:
        # Resolve per-workspace email adapter; falls back to SendGridAdapter().
        adapter = resolve_email_adapter(
            db, workspace_id, default_factory=SendGridAdapter
        )
        idempotency_key = f"postcall:{sess.id}"
        try:
            await adapter.send_email(
                to=to_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                idempotency_key=idempotency_key,
            )
            email_sent = True
            logger.info("Sent post-call summary for session=%s to %s", sess.id, to_email)
        except Exception:
            logger.exception(
                "Failed to send post-call email for session=%s", sess.id
            )
            # Intentionally not re-raising: mark processed to avoid re-processing loop.

    # Flag scheduling follow-up directly on the CallSession
    if sess.scheduling_interest:
        sess.postcall_status = "scheduling_pending"
        logger.info("Flagged session=%s for scheduling follow-up", sess.id)

    # Mark processed and persist audit trail in the same transaction
    sess.post_call_processed = True
    db.add(sess)

    audit = AuditEvent(
        event_name="call.postcall_processed",
        workspace_id=workspace_id,
        resource_type="call_session",
        resource_id=str(sess.id),
        payload={
            "call_request_id": str(req.id),
            "outcome": summary["outcome"],
            "scheduling_intent": summary["scheduling_intent"],
            "summary_email_sent": email_sent,
            "team_email": to_email or "",
        },
    )
    db.add(audit)


# ---------------------------------------------------------------------------
# Polling entry-point (called by APScheduler)
# ---------------------------------------------------------------------------

async def process_completed_calls() -> None:
    """Query COMPLETED CallSessions not yet processed and handle each one.

    Uses SELECT … FOR UPDATE SKIP LOCKED so multiple worker replicas can
    run without double-processing the same row.
    """
    logger.debug("postcall_worker: starting poll")
    processed = 0

    with Session(engine) as db:
        rows = db.exec(
            select(CallRequest, CallSession)
            .join(CallSession, CallRequest.id == CallSession.call_request_id)
            .where(
                CallRequest.status == CallRequestStatus.completed,
                CallSession.post_call_processed == False,  # noqa: E712
            )
            .order_by(CallSession.created_at)
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ).all()

        if not rows:
            logger.debug("postcall_worker: no pending sessions")
            return

        for req, sess in rows:
            try:
                await _process_session(db, req, sess)
                processed += 1
            except Exception:
                logger.exception(
                    "postcall_worker: unhandled error for session=%s", sess.id
                )
                db.rollback()
                # Continue with next row rather than aborting the entire batch

        db.commit()

    logger.info("postcall_worker: processed %d session(s)", processed)
