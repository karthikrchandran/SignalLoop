"""FastAPI router: ``scheduling`` endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import WorkspaceIdDep
from app.core.config import settings
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.scheduling import service as scheduling_service
from app.domain.scheduling.schemas import (
    SchedulingRequestCreate,
    SchedulingRequestPublic,
    SchedulingRequestsPublic,
    SchedulingRequestUpdate,
)
from app.domain_models import Campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduling", tags=["scheduling"])


# ---------------------------------------------------------------------------
# List / detail / update
# ---------------------------------------------------------------------------


@router.get("/requests", response_model=SchedulingRequestsPublic)
def list_requests(
    session: SessionDep,
    _current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    status_filter: str | None = Query(default=None, alias="status"),
    campaign_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
) -> SchedulingRequestsPublic:
    """List scheduling requests for the workspace."""
    rows, total = scheduling_service.list_scheduling_requests(
        session,
        workspace_id=workspace_id,
        status=status_filter,
        campaign_id=campaign_id,
        skip=skip,
        limit=limit,
    )
    return SchedulingRequestsPublic(
        data=[SchedulingRequestPublic.model_validate(r) for r in rows],
        count=total,
    )


@router.get("/requests/{request_id}", response_model=SchedulingRequestPublic)
def get_request(
    request_id: uuid.UUID,
    session: SessionDep,
    _current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Get a single scheduling request."""
    req = scheduling_service.get_scheduling_request_or_404(session, request_id)
    # Verify workspace ownership
    campaign = session.get(Campaign, req.campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Scheduling request not found")
    return SchedulingRequestPublic.model_validate(req)


@router.post("/requests", response_model=SchedulingRequestPublic, status_code=status.HTTP_201_CREATED)
def create_request(
    data: SchedulingRequestCreate,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Manually create a scheduling request."""
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == data.campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    req = scheduling_service.create_scheduling_request(session, data=data)
    append_audit_event_to_session(
        session,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        event_type="scheduling_request.created",
        aggregate_id=req.id,
        aggregate_type="SchedulingRequest",
        workspace_id=workspace_id,
        details={"source": data.source},
    )
    session.commit()
    session.refresh(req)
    return SchedulingRequestPublic.model_validate(req)


@router.patch("/requests/{request_id}", response_model=SchedulingRequestPublic)
def update_request(
    request_id: uuid.UUID,
    data: SchedulingRequestUpdate,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
) -> SchedulingRequestPublic:
    """Update status, meeting link, assignee, or notes on a scheduling request."""
    req = scheduling_service.get_scheduling_request_or_404(session, request_id)
    campaign = session.get(Campaign, req.campaign_id)
    if not campaign or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Scheduling request not found")

    updated = scheduling_service.update_scheduling_request(
        session, request_id=request_id, data=data
    )
    append_audit_event_to_session(
        session,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        event_type="scheduling_request.updated",
        aggregate_id=updated.id,
        aggregate_type="SchedulingRequest",
        workspace_id=workspace_id,
        details=data.model_dump(exclude_none=True),
    )
    session.commit()
    session.refresh(updated)
    return SchedulingRequestPublic.model_validate(updated)


# ---------------------------------------------------------------------------
# Calendly webhook
# ---------------------------------------------------------------------------


@router.post("/webhooks/calendly", status_code=status.HTTP_200_OK)
async def calendly_webhook(
    request: Request,
    session: SessionDep,
) -> dict[str, str]:
    """Receive Calendly invitee.created events and mark the linked request as booked."""
    body = await request.body()
    signature = request.headers.get("Calendly-Webhook-Signature", "")

    signing_key = settings.CALENDLY_WEBHOOK_SIGNING_KEY
    if not signing_key:
        raise HTTPException(
            status_code=503, detail="Calendly webhook signing key is not configured"
        )
    if not scheduling_service.verify_calendly_signature(
        body, signature, signing_key
    ):
        raise HTTPException(status_code=403, detail="Invalid Calendly webhook signature")

    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("event", "")
    if event_type != "invitee.created":
        # Acknowledge non-booking events without action
        return {"status": "ignored", "event": event_type}

    event_payload = payload.get("payload", {})
    tracking = event_payload.get("tracking", {})

    # We embed the scheduling_request_id in the Calendly link as utm_content
    request_id_str = tracking.get("utm_content")
    if not request_id_str:
        logger.warning("Calendly webhook: no utm_content in tracking, cannot link request")
        return {"status": "unlinked"}
    workspace_id = str(tracking.get("utm_source") or "").strip()
    if not workspace_id:
        raise HTTPException(status_code=400, detail="Missing scheduling workspace token")

    try:
        request_id = uuid.UUID(request_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scheduling request id in utm_content")

    calendly_event = event_payload.get("event", {})
    event_uri = calendly_event.get("uri", "")
    start_time_str = calendly_event.get("start_time")
    try:
        meeting_dt = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now(timezone.utc)
    except (ValueError, TypeError):
        meeting_dt = datetime.now(timezone.utc)

    scheduling_service.handle_calendly_booking(
        session,
        workspace_id=workspace_id,
        request_id=request_id,
        calendly_event_id=event_uri,
        meeting_datetime=meeting_dt,
    )

    logger.info("Calendly booking confirmed for scheduling_request=%s", request_id)
    return {"status": "booked"}
