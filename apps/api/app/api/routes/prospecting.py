from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.audit_events import audit_actor_role
from app.domain.prospecting.schemas import (
    ProspectingBulkResearchRequest,
    ProspectingEnrollmentPublic,
    ProspectingEnrollmentRequest,
    ProspectingReadyContactsPublic,
    ProspectingResearchListPublic,
    ProspectingResearchPublic,
    ProspectingResearchRequest,
)
from app.domain.prospecting.service import (
    ProspectingCampaignNotFoundError,
    ProspectingContactNotFoundError,
    ProspectingSequenceNotFoundError,
    create_bulk_prospecting_snapshots,
    create_prospecting_snapshot,
    enroll_selected_prospects,
    list_prospecting_snapshots,
    list_ready_contacts,
    snapshot_to_public,
)

router = APIRouter(prefix="/prospecting", tags=["prospecting"])


@router.get("/ready-contacts", response_model=ProspectingReadyContactsPublic, dependencies=[Depends(require_admin)])
def read_ready_contacts(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    search: Annotated[str | None, Query(max_length=255)] = None,
    only_handoffs: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ProspectingReadyContactsPublic:
    """Return workspace contacts ranked for prospecting handoff."""
    contacts = list_ready_contacts(
        session,
        workspace_id=workspace_id,
        search=search,
        only_handoffs=only_handoffs,
        limit=limit,
    )
    return ProspectingReadyContactsPublic(data=contacts, count=len(contacts))


@router.post("/research", response_model=ProspectingResearchPublic, dependencies=[Depends(require_admin)])
async def run_prospecting_research(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: ProspectingResearchRequest,
) -> ProspectingResearchPublic:
    """Run prospecting research for a workspace contact."""
    try:
        snapshot = await create_prospecting_snapshot(
            session=session,
            workspace_id=workspace_id,
            contact_id=body.contact_id,
            company_url=body.company_url,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
        )
    except ProspectingContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    return snapshot_to_public(snapshot)


@router.post("/research/bulk", response_model=ProspectingResearchListPublic, dependencies=[Depends(require_admin)])
async def run_bulk_prospecting_research(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: ProspectingBulkResearchRequest,
) -> ProspectingResearchListPublic:
    """Run prospecting research for selected workspace contacts."""
    try:
        snapshots = await create_bulk_prospecting_snapshots(
            session=session,
            workspace_id=workspace_id,
            contact_ids=body.contact_ids,
            company_url=body.company_url,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
        )
    except ProspectingContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ProspectingResearchListPublic(
        data=[snapshot_to_public(snapshot) for snapshot in snapshots],
        count=len(snapshots),
    )


@router.post("/enroll", response_model=ProspectingEnrollmentPublic, dependencies=[Depends(require_admin)])
def enroll_prospecting_contacts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: ProspectingEnrollmentRequest,
) -> ProspectingEnrollmentPublic:
    """Add selected prospects to campaign outreach and optionally a sequence."""
    try:
        return enroll_selected_prospects(
            session=session,
            workspace_id=workspace_id,
            contact_ids=body.contact_ids,
            campaign_id=body.campaign_id,
            sequence_id=body.sequence_id,
            actor_id=current_user.id,
            actor_role=audit_actor_role(current_user),
        )
    except ProspectingContactNotFoundError:
        raise HTTPException(status_code=404, detail="Contact not found")
    except ProspectingCampaignNotFoundError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    except ProspectingSequenceNotFoundError:
        raise HTTPException(status_code=404, detail="Sequence not found")


@router.get("/research", response_model=ProspectingResearchListPublic, dependencies=[Depends(require_admin)])
def read_prospecting_research(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    contact_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> ProspectingResearchListPublic:
    """Return recent prospecting research snapshots."""
    snapshots = list_prospecting_snapshots(
        session=session,
        workspace_id=workspace_id,
        contact_id=contact_id,
        limit=limit,
    )
    return ProspectingResearchListPublic(
        data=[snapshot_to_public(snapshot) for snapshot in snapshots],
        count=len(snapshots),
    )
