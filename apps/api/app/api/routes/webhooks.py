"""FastAPI router: ``webhooks`` endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from app.api.deps import SessionDep
from app.domain.audit.audit_events import append_audit_event_to_session
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
from app.domain.signals.trigger_service import process_signal
from app.domain.timeline.timeline_service import invalidate_timeline_cache
from app.domain_models import NotificationProvider, ProviderEventLog
from app.infrastructure.providers.sendgrid import SendGridAdapter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# SendGrid event type mappings
TERMINAL_EVENTS = {"bounce", "dropped", "spamreport", "unsubscribe"}
POSITIVE_EVENTS = {"delivered", "open", "click"}


@router.post("/sendgrid")
async def handle_sendgrid_webhook(request: Request, session: SessionDep) -> dict[str, str]:
    """Handle sendgrid webhook."""
    body = await request.body()
    signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature", "")
    timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp", "")

    if not SendGridAdapter.verify_webhook_signature(body, signature, timestamp):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    events: list[dict[str, Any]] = await request.json()
    adapter = SendGridAdapter()
    timeline_cache_targets: set[tuple[uuid.UUID, uuid.UUID]] = set()
    seen_provider_events: set[tuple[str, str]] = set()

    for raw_event in events:
        try:
            normalized = await adapter.normalize_webhook_event(raw_event)
            provider_msg_id = normalized["provider_message_id"]
            event_type = normalized["event_type"]
            provider_event_id = normalized.get("provider_event_id") or raw_event.get("sg_event_id", "")

            if not provider_msg_id:
                continue
            event_workspace_id = str(normalized.get("workspace_id") or "")
            send_request = _find_send_request_for_webhook(
                session,
                provider_message_id=provider_msg_id,
                workspace_id=event_workspace_id or None,
            )

            if not send_request:
                logger.warning("No SendRequest found for message_id=%s", provider_msg_id)
                continue

            workspace_id = send_request.workspace_id
            provider_event_key = (workspace_id, provider_event_id)
            if provider_event_id:
                if provider_event_key in seen_provider_events or _provider_event_seen(
                    session,
                    workspace_id,
                    provider_event_id,
                ):
                    logger.info(
                        "Skipping replayed SendGrid event %s in workspace %s",
                        provider_event_id,
                        workspace_id,
                    )
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
            timeline_cache_targets.update(
                await _process_event(session, send_request, event_type, normalized, raw_event)
            )
            if provider_event_id:
                session.add(
                    ProviderEventLog(
                        workspace_id=workspace_id,
                        provider=NotificationProvider.sendgrid,
                        provider_event_id=provider_event_id,
                        event_type=event_type,
                        raw_payload=raw_event,
                        normalized_event=normalized,
                    )
                )
                seen_provider_events.add(provider_event_key)
        except Exception:
            logger.exception("Error processing webhook event: %s", raw_event.get("sg_event_id", "unknown"))

    session.commit()
    for contact_id, campaign_id in timeline_cache_targets:
        await invalidate_timeline_cache(request, contact_id, campaign_id)
    return {"status": "ok"}


def _find_send_request_for_webhook(
    session: Session,
    *,
    provider_message_id: str,
    workspace_id: str | None,
) -> SendRequest | None:
    statement = select(SendRequest).where(
        SendRequest.provider_message_id == provider_message_id
    )
    if workspace_id is not None:
        statement = statement.where(SendRequest.workspace_id == workspace_id)
    matches = session.exec(statement.limit(2)).all()
    if len(matches) != 1:
        logger.warning(
            "Webhook message_id=%s matched %d send requests; refusing ambiguous event",
            provider_message_id,
            len(matches),
        )
        return None
    return matches[0]


def _provider_event_seen(
    session: Session,
    workspace_id: str,
    provider_event_id: str,
) -> bool:
    return session.exec(
        select(ProviderEventLog.id).where(
            ProviderEventLog.workspace_id == workspace_id,
            ProviderEventLog.provider == NotificationProvider.sendgrid,
            ProviderEventLog.provider_event_id == provider_event_id,
        )
    ).first() is not None


async def _process_event(
    session: Session,
    send_request: SendRequest,
    event_type: str,
    normalized: dict[str, Any],
    raw_event: dict[str, Any],
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    timeline_cache_targets: set[tuple[uuid.UUID, uuid.UUID]] = set()
    workspace_id = _workspace_for_send_request(session, send_request)
    if event_type == "delivered":
        send_request.status = SendRequestStatus.sent
        send_request.sent_at = datetime.now(timezone.utc)

    elif event_type in ("bounce", "dropped"):
        send_request.status = SendRequestStatus.failed
        _stop_contact_sequence(session, send_request, signal_type="hard_bounce")
        if target := await _emit_signal(session, send_request, "hard_bounce", confidence=1.0):
            timeline_cache_targets.add(target)

    elif event_type in ("spamreport", "unsubscribe"):
        _stop_contact_sequence(session, send_request, signal_type=event_type)
        _add_suppression(session, normalized["contact_identifier"], event_type, workspace_id)
        if target := await _emit_signal(session, send_request, event_type, confidence=1.0):
            timeline_cache_targets.add(target)

    elif event_type == "replied":
        reply_text = raw_event.get("text", "") or raw_event.get("body", "")
        result = detect_email_signal(reply_text)
        if result.signal_type == "email_positive_reply":
            _pause_contact_sequence(session, send_request, result)
            if target := await _emit_signal(
                session, send_request, result.signal_type, confidence=result.confidence
            ):
                timeline_cache_targets.add(target)

    session.add(send_request)
    return timeline_cache_targets


def _workspace_for_send_request(
    _session: Session,
    send_request: SendRequest,
) -> str:
    return send_request.workspace_id


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


async def _emit_signal(
    session: Session,
    send_request: SendRequest,
    signal_type: str,
    *,
    confidence: float,
) -> tuple[uuid.UUID, uuid.UUID] | None:
    state = session.get(ContactSequenceState, send_request.contact_sequence_state_id)
    if not state:
        return None
    # Get campaign_id from the sequence
    seq = session.get(EmailSequence, state.sequence_id)
    if not seq:
        return None
    signal = SignalEvent(
        contact_id=state.contact_id,
        campaign_id=seq.campaign_id,
        channel="email",
        signal_type=signal_type,
        confidence=confidence,
        source_event_id=send_request.id,
    )
    session.add(signal)
    await process_signal(session, signal)
    return state.contact_id, seq.campaign_id


def _add_suppression(session: Session, email: str, reason: str, workspace_id: str) -> None:
    existing = session.exec(
        select(EmailSuppression).where(
            EmailSuppression.workspace_id == workspace_id,
            EmailSuppression.email == email,
            EmailSuppression.reason == reason,
        )
    ).first()
    if not existing:
        session.add(
            EmailSuppression(
                workspace_id=workspace_id,
                email=email,
                reason=reason,
            )
        )
        append_audit_event_to_session(
            session,
            event_name="suppression_added",
            workspace_id=workspace_id,
            actor_role="system",
            resource_type="email",
            resource_id=email,
            payload={"email": email, "reason": reason},
        )
