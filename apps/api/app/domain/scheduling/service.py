"""Domain service: ``scheduling``."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.domain.contacts.progression_service import transition_contact_state
from app.domain.scheduling.models import (
    SchedulingRequest,
    SchedulingRequestSource,
    SchedulingRequestStatus,
)
from app.domain.scheduling.schemas import (
    SchedulingRequestCreate,
    SchedulingRequestUpdate,
)
from app.domain_models import Campaign, Contact, ContactProgressionState
from app.integrations.ecrm_workflow_events import emit_event


def _now() -> datetime:
    return datetime.now(timezone.utc)


CALENDLY_STATE_MIN_TTL_SECONDS = 60
CALENDLY_STATE_MAX_TTL_SECONDS = 30 * 24 * 60 * 60


def mint_calendly_state(
    request_id: uuid.UUID,
    workspace_id: str,
    signing_key: str,
    *,
    expires_at: int | None = None,
    ttl_seconds: int = 24 * 60 * 60,
) -> str:
    bounded_ttl = max(
        CALENDLY_STATE_MIN_TTL_SECONDS,
        min(ttl_seconds, CALENDLY_STATE_MAX_TTL_SECONDS),
    )
    payload = json.dumps(
        {
            "requestId": str(request_id),
            "workspace": workspace_id,
            "exp": expires_at or int(time.time()) + bounded_ttl,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_calendly_state(token: str, signing_key: str) -> tuple[uuid.UUID, str] | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(payload, dict) or int(payload.get("exp", 0)) < int(time.time()):
            return None
        workspace_id = payload.get("workspace")
        if not isinstance(workspace_id, str) or not workspace_id.strip():
            return None
        return uuid.UUID(str(payload.get("requestId"))), workspace_id.strip()
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
        return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def create_scheduling_request(
    session: Session,
    *,
    data: SchedulingRequestCreate,
    commit: bool = True,
) -> SchedulingRequest:
    """Create a new scheduling request."""
    campaign = session.get(Campaign, data.campaign_id)
    if campaign is None:
        raise ValueError("scheduling campaign not found")
    contact = session.get(Contact, data.contact_id)
    if contact is not None and contact.workspace_id != campaign.workspace_id:
        raise ValueError("scheduling contact workspace mismatch")
    req = SchedulingRequest(
        workspace_id=campaign.workspace_id,
        contact_id=data.contact_id,
        campaign_id=data.campaign_id,
        signal_event_id=data.signal_event_id,
        source=data.source,
        assigned_to_email=data.assigned_to_email,
        notes=data.notes,
    )
    session.add(req)
    if commit:
        session.commit()
        session.refresh(req)
    return req


def get_scheduling_request_or_404(
    session: Session, request_id: uuid.UUID
) -> SchedulingRequest:
    """Return a scheduling request or raise 404."""
    req = session.get(SchedulingRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Scheduling request not found")
    return req


def list_scheduling_requests(
    session: Session,
    *,
    workspace_id: str,
    status: str | None = None,
    campaign_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[SchedulingRequest], int]:
    """Return scheduling requests filtered by workspace, status, and campaign."""
    base_query = (
        select(SchedulingRequest)
        .join(Contact, SchedulingRequest.contact_id == Contact.id)
        .join(Campaign, SchedulingRequest.campaign_id == Campaign.id)
        .where(
            SchedulingRequest.workspace_id == workspace_id,
            Campaign.workspace_id == workspace_id,
        )
    )

    if status:
        base_query = base_query.where(SchedulingRequest.status == status)
    if campaign_id:
        base_query = base_query.where(SchedulingRequest.campaign_id == campaign_id)

    count_query = select(func.count()).select_from(base_query.subquery())
    total = session.exec(count_query).one()

    rows = session.exec(
        base_query.order_by(SchedulingRequest.created_at.desc())  # type: ignore[attr-defined]
        .offset(skip)
        .limit(limit)
    ).all()

    return list(rows), total


def update_scheduling_request(
    session: Session,
    *,
    request_id: uuid.UUID,
    data: SchedulingRequestUpdate,
    commit: bool = True,
) -> SchedulingRequest:
    """Update a scheduling request."""
    req = get_scheduling_request_or_404(session, request_id)

    if data.status is not None:
        req.status = data.status
    if data.meeting_link is not None:
        req.meeting_link = data.meeting_link
        if req.status == SchedulingRequestStatus.pending:
            req.status = SchedulingRequestStatus.link_sent
    if data.assigned_to_email is not None:
        req.assigned_to_email = data.assigned_to_email
    if data.notes is not None:
        req.notes = data.notes

    req.updated_at = _now()
    session.add(req)
    if commit:
        session.commit()
        session.refresh(req)
    return req


# ---------------------------------------------------------------------------
# Calendly webhook
# ---------------------------------------------------------------------------


def verify_calendly_signature(
    body: bytes,
    signature_header: str,
    signing_key: str,
    *,
    max_age_seconds: int = 5 * 60,
) -> bool:
    """Verify a Calendly webhook HMAC-SHA256 signature.

    Calendly signs payloads as ``t=<timestamp>,v1=<hmac_hex>`` where the
    signed message is ``<timestamp>.<body>``.
    """
    try:
        parts = dict(part.split("=", 1) for part in signature_header.split(","))
        timestamp = parts.get("t", "")
        v1 = parts.get("v1", "")
    except (ValueError, AttributeError):
        return False

    try:
        if abs(int(time.time()) - int(timestamp)) > max_age_seconds:
            return False
    except ValueError:
        return False
    signed_message = f"{timestamp}.{body.decode('utf-8', errors='replace')}"
    expected = hmac.new(
        signing_key.encode(),
        signed_message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, v1)


def handle_calendly_booking(
    session: Session,
    *,
    workspace_id: str,
    request_id: uuid.UUID,
    calendly_event_id: str,
    meeting_datetime: datetime,
    commit: bool = True,
) -> SchedulingRequest:
    """Mark a scheduling request as booked from a Calendly webhook and advance
    the contact's campaign progression to the ``booked`` state."""
    req = session.exec(
        select(SchedulingRequest).where(
            SchedulingRequest.id == request_id,
            SchedulingRequest.workspace_id == workspace_id,
        ).with_for_update()
    ).first()
    if req is None:
        raise HTTPException(status_code=404, detail="Scheduling request not found")
    if req.status == SchedulingRequestStatus.booked:
        if req.calendly_event_id != calendly_event_id:
            raise HTTPException(status_code=409, detail="Scheduling request already booked")
        return req

    req.status = SchedulingRequestStatus.booked
    req.calendly_event_id = calendly_event_id
    req.meeting_datetime = meeting_datetime
    req.updated_at = _now()
    session.add(req)

    # Advance contact progression → booked (best-effort, ignore invalid transitions)
    try:
        transition_contact_state(
            session,
            contact_id=req.contact_id,
            campaign_id=req.campaign_id,
            to_state=ContactProgressionState.booked,
            reason="calendly_booking_confirmed",
        )
    except Exception:
        pass

    if commit:
        session.commit()
        session.refresh(req)

    try:
        emit_event(
            {
                "sourceApp": "emailvoice",
                "sourceEventType": "meeting_booked",
                "sourceEventId": f"scheduling-booked:{req.id}",
                "entityType": "LEAD",
                "entityId": str(req.contact_id),
                "relatedRecordType": "LEAD",
                "relatedRecordId": str(req.contact_id),
                "summary": "Meeting booked in EmailVoice",
                "payload": {
                    "requestId": str(req.id),
                    "contactId": str(req.contact_id),
                    "campaignId": str(req.campaign_id),
                    "meetingTime": req.meeting_datetime.isoformat() if req.meeting_datetime else None,
                    "status": req.status.value
                    if isinstance(req.status, SchedulingRequestStatus)
                    else str(req.status),
                },
                "occurredAt": req.updated_at.isoformat(),
            }
        )
    except Exception:
        pass

    return req


def create_from_call_session(
    session: Session,
    *,
    contact_id: uuid.UUID,
    campaign_id: uuid.UUID,
    signal_event_id: uuid.UUID | None = None,
    commit: bool = True,
) -> SchedulingRequest:
    """Convenience factory called by the post-call worker when scheduling_interest is True."""
    return create_scheduling_request(
        session,
        data=SchedulingRequestCreate(
            contact_id=contact_id,
            campaign_id=campaign_id,
            signal_event_id=signal_event_id,
            source=SchedulingRequestSource.voice_call,
        ),
        commit=commit,
    )
