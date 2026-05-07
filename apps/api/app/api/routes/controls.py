"""FastAPI router: ``controls`` endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.policies.global_control_service import apply_pause_state
from app.domain_models import (
    Campaign,
    CampaignStatus,
    ControlStatePublic,
    GlobalControlState,
    PauseRequest,
)

router = APIRouter(tags=["controls"])


def _find_control_state(session: SessionDep, workspace_id: str, campaign_id: uuid.UUID | None = None) -> GlobalControlState | None:
    return session.exec(
        select(GlobalControlState).where(GlobalControlState.workspace_id == workspace_id, GlobalControlState.campaign_id == campaign_id)
    ).first()


@router.post("/controls/pause", response_model=ControlStatePublic, dependencies=[Depends(require_admin)])
async def pause_global(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: PauseRequest,
) -> ControlStatePublic:
    """Pause global."""
    action_at = datetime.now(UTC)
    state = _find_control_state(session, workspace_id) or GlobalControlState(workspace_id=workspace_id)
    for key, value in apply_pause_state(body.paused_reason).items():
        setattr(state, key, value)
    state.paused_by = current_user.id
    session.add(state)
    actor_role = audit_actor_role(current_user)
    append_audit_event_to_session(
        session,
        event_name="global_pause_applied",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=actor_role,
        resource_type="control_state",
        resource_id=str(state.id),
        payload={"paused_reason": body.paused_reason},
    )
    session.commit()
    session.refresh(state)
    return ControlStatePublic(
        id=state.id,
        paused=state.paused,
        paused_reason=state.paused_reason,
        paused_at=state.paused_at,
        action="pause",
        actor_id=current_user.id,
        actor_role=actor_role,
        action_at=action_at,
    )


@router.post("/controls/resume", response_model=ControlStatePublic, dependencies=[Depends(require_admin)])
async def resume_global(
    *, session: SessionDep, current_user: CurrentUser, workspace_id: WorkspaceIdDep, _: IdempotencyKeyDep
) -> ControlStatePublic:
    """Resume global."""
    action_at = datetime.now(UTC)
    state = _find_control_state(session, workspace_id)
    if not state:
        raise HTTPException(status_code=404, detail="Global control state not found")
    state.paused = False
    state.paused_reason = None
    state.paused_at = None
    session.add(state)
    actor_role = audit_actor_role(current_user)
    append_audit_event_to_session(
        session,
        event_name="global_resume_applied",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=actor_role,
        resource_type="control_state",
        resource_id=str(state.id),
        payload={},
    )
    session.commit()
    session.refresh(state)
    return ControlStatePublic(
        id=state.id,
        paused=state.paused,
        paused_reason=state.paused_reason,
        paused_at=state.paused_at,
        action="resume",
        actor_id=current_user.id,
        actor_role=actor_role,
        action_at=action_at,
    )


@router.post("/campaigns/{campaign_id}/pause", response_model=ControlStatePublic, dependencies=[Depends(require_admin)])
async def pause_campaign(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: PauseRequest,
) -> ControlStatePublic:
    """Pause campaign."""
    action_at = datetime.now(UTC)
    campaign = session.exec(select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    state = _find_control_state(session, workspace_id, campaign_id) or GlobalControlState(workspace_id=workspace_id, campaign_id=campaign_id)
    for key, value in apply_pause_state(body.paused_reason).items():
        setattr(state, key, value)
    state.paused_by = current_user.id
    campaign.status = CampaignStatus.paused
    session.add(campaign)
    session.add(state)
    actor_role = audit_actor_role(current_user)
    append_audit_event_to_session(
        session,
        event_name="campaign_paused",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=actor_role,
        resource_type="campaign",
        resource_id=str(campaign_id),
        payload={"campaign_id": str(campaign_id), "paused_reason": body.paused_reason},
    )
    session.commit()
    session.refresh(state)
    return ControlStatePublic(
        id=state.id,
        paused=state.paused,
        paused_reason=state.paused_reason,
        paused_at=state.paused_at,
        action="pause",
        actor_id=current_user.id,
        actor_role=actor_role,
        action_at=action_at,
    )


@router.post("/campaigns/{campaign_id}/resume", response_model=ControlStatePublic, dependencies=[Depends(require_admin)])
async def resume_campaign(
    *, session: SessionDep, current_user: CurrentUser, campaign_id: uuid.UUID, workspace_id: WorkspaceIdDep, _: IdempotencyKeyDep
) -> ControlStatePublic:
    """Resume campaign."""
    action_at = datetime.now(UTC)
    campaign = session.exec(select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    state = _find_control_state(session, workspace_id, campaign_id)
    if not state:
        raise HTTPException(status_code=404, detail="Campaign control state not found")
    state.paused = False
    state.paused_reason = None
    state.paused_at = None
    campaign.status = CampaignStatus.draft
    session.add(campaign)
    session.add(state)
    actor_role = audit_actor_role(current_user)
    append_audit_event_to_session(
        session,
        event_name="campaign_activated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=actor_role,
        resource_type="campaign",
        resource_id=str(campaign_id),
        payload={"campaign_id": str(campaign_id)},
    )
    session.commit()
    session.refresh(state)
    return ControlStatePublic(
        id=state.id,
        paused=state.paused,
        paused_reason=state.paused_reason,
        paused_at=state.paused_at,
        action="resume",
        actor_id=current_user.id,
        actor_role=actor_role,
        action_at=action_at,
    )
