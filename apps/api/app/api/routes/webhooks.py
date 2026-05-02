from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.domain.audit.audit_events import append_audit_event
from app.domain.sequences.models import (
    ContactSequenceState,
    EmailEvent,
    EmailSequence,
    SendRequest,
    SendRequestStatus,
    SequenceStatus,
)
from app.domain.sequences.suppression import EmailSuppression
from app.domain.signals.models import SignalEvent
from app.domain.signals.signal_detector import detect_email_signal
from app.infrastructure.providers.sendgrid import SendGridAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# SendGrid event type mappings
TERMINAL_EVENTS = {"bounce", "dropped", "spamreport", "unsubscribe"}
POSITIVE_EVENTS = {"delivered", "open", "click"}


@router.post("/sendgrid")
async def handle_sendgrid_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    body = await request.body()
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")

    if not SendGridAdapter.verify_webhook_signature(body, signature, timestamp):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    events: list[dict[str, Any]] = await request.json()
    adapter = SendGridAdapter()

    for raw_event in events:
        try:
            normalized = await adapter.normalize_webhook_event(raw_event)
            provider_msg_id = normalized["provider_message_id"]
            event_type = normalized["event_type"]

            if not provider_msg_id:
                continue

            # Find matching SendRequest
            send_request = session.exec(
                select(SendRequest).where(
                    SendRequest.provider_message_id == provider_msg_id
                )
            ).first()

            if not send_request:
                logger.warning("No SendRequest found for message_id=%s", provider_msg_id)
                continue

            # Store the event
            email_event = EmailEvent(
                send_request_id=send_request.id,
                event_type=event_type,
                timestamp=datetime.fromtimestamp(
                    float(raw_event.get("timestamp", 0)), tz=timezone.utc
                ),
                raw_payload=raw_event,
            )
            session.add(email_event)

            # Process event effects
            _process_event(session, send_request, event_type, normalized, raw_event)
        except Exception:
            logger.exception("Error processing webhook event: %s", raw_event.get("sg_event_id", "unknown"))

    session.commit()
    return {"status": "ok"}


def _process_event(
    session: Session,
    send_request: SendRequest,
    event_type: str,
    normalized: dict[str, Any],
    raw_event: dict[str, Any],
) -> None:
    if event_type == "delivered":
        send_request.status = SendRequestStatus.sent
        send_request.sent_at = datetime.now(timezone.utc)

    elif event_type in ("bounce", "dropped"):
        send_request.status = SendRequestStatus.failed
        _stop_contact_sequence(session, send_request, signal_type="hard_bounce")
        _emit_signal(session, send_request, "hard_bounce", confidence=1.0)

    elif event_type in ("spamreport", "unsubscribe"):
        _stop_contact_sequence(session, send_request, signal_type=event_type)
        _add_suppression(session, normalized["contact_identifier"], event_type)
        _emit_signal(session, send_request, event_type, confidence=1.0)

    elif event_type == "replied":
        reply_text = raw_event.get("text", "") or raw_event.get("body", "")
        result = detect_email_signal(reply_text)
        if result.signal_type == "email_positive_reply":
            _pause_contact_sequence(session, send_request, result)
            _emit_signal(
                session, send_request, result.signal_type, confidence=result.confidence
            )

    session.add(send_request)


def _stop_contact_sequence(
    session: Session, send_request: SendRequest, *, signal_type: str
) -> None:
    state = session.get(ContactSequenceState, send_request.contact_sequence_state_id)
    if state and state.status == SequenceStatus.active:
        state.status = SequenceStatus.stopped
        state.signal_type = signal_type
        state.signal_detected_at = datetime.now(timezone.utc)
        session.add(state)


def _pause_contact_sequence(
    session: Session,
    send_request: SendRequest,
    signal_result: Any,
) -> None:
    state = session.get(ContactSequenceState, send_request.contact_sequence_state_id)
    if state and state.status == SequenceStatus.active:
        state.status = SequenceStatus.paused
        state.signal_type = signal_result.signal_type
        state.signal_detected_at = datetime.now(timezone.utc)
        session.add(state)


def _emit_signal(
    session: Session,
    send_request: SendRequest,
    signal_type: str,
    *,
    confidence: float,
) -> None:
    state = session.get(ContactSequenceState, send_request.contact_sequence_state_id)
    if not state:
        return
    # Get campaign_id from the sequence
    seq = session.get(EmailSequence, state.sequence_id)
    if not seq:
        return
    signal = SignalEvent(
        contact_id=state.contact_id,
        campaign_id=seq.campaign_id,
        channel="email",
        signal_type=signal_type,
        confidence=confidence,
        source_event_id=send_request.id,
    )
    session.add(signal)


def _add_suppression(session: Session, email: str, reason: str, workspace_id: str = "system") -> None:
    existing = session.exec(
        select(EmailSuppression).where(
            EmailSuppression.email == email,
            EmailSuppression.reason == reason,
        )
    ).first()
    if not existing:
        session.add(EmailSuppression(email=email, reason=reason))
        asyncio.create_task(
            append_audit_event(
                event_name="suppression_added",
                workspace_id=workspace_id,
                resource_type="email",
                resource_id=email,
                payload={"email": email, "reason": reason},
            )
        )
