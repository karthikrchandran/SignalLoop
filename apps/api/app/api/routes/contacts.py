"""Contact timeline API endpoints (Story 5.1)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.timeline.timeline_service import (
    get_contact_timeline,
    get_timeline_event_detail,
)
from app.domain_models import (
    Contact,
    TimelineEventDetailPublic,
    TimelinePagePublic,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _get_contact_or_404(
    session: Session,
    contact_id: uuid.UUID,
    workspace_id: str,
) -> Contact:
    contact = session.exec(
        select(Contact).where(
            Contact.id == contact_id,
            Contact.workspace_id == workspace_id,
        )
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get(
    "/{contact_id}/timeline",
    response_model=TimelinePagePublic,
    dependencies=[Depends(require_admin)],
)
async def get_contact_timeline_route(
    contact_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
    campaign_id: Annotated[uuid.UUID | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    event_type: Annotated[str | None, Query(max_length=128)] = None,
    from_dt: Annotated[datetime | None, Query(alias="from")] = None,
    to_dt: Annotated[datetime | None, Query(alias="to")] = None,
) -> TimelinePagePublic:
    """Return a paginated, chronologically sorted timeline for a contact.

    Aggregates from contact_state_history, contact_events, and routing_decisions.
    First unfiltered page is Redis-cached for 30 s (NFR2 / p95 < 3 s).
    """
    _get_contact_or_404(session, contact_id, workspace_id)
    return await get_contact_timeline(
        session=session,
        request=request,
        contact_id=contact_id,
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        page=page,
        limit=limit,
        event_type=event_type,
        from_dt=from_dt,
        to_dt=to_dt,
    )


@router.get(
    "/{contact_id}/timeline/{event_id}",
    response_model=TimelineEventDetailPublic,
    dependencies=[Depends(require_admin)],
)
def get_contact_timeline_event(
    contact_id: uuid.UUID,
    event_id: str,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    _current_user: CurrentUser,
) -> TimelineEventDetailPublic:
    """Return full explainability detail for one timeline entry."""
    _get_contact_or_404(session, contact_id, workspace_id)
    try:
        detail = get_timeline_event_detail(
            session=session,
            contact_id=contact_id,
            workspace_id=workspace_id,
            event_id=event_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_id format")
    if detail is None:
        raise HTTPException(status_code=404, detail="Timeline event not found")
    return detail
