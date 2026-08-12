"""FastAPI router: ``controls`` endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.idempotency import run_idempotent_mutation
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
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: PauseRequest,
) -> ControlStatePublic:
    """Pause global."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="controls:global:pause",
        request_payload=body.model_dump(),
        mutation=lambda: _pause_global_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _pause_global_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    body: PauseRequest,
) -> ControlStatePublic:
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
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
) -> ControlStatePublic:
    """Resume global."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="controls:global:resume",
        mutation=lambda: _resume_global_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
        ),
    )


def _resume_global_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
) -> ControlStatePublic:
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
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: PauseRequest,
) -> ControlStatePublic:
    """Pause campaign."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation=f"controls:campaign:{campaign_id}:pause",
        request_payload={"campaign_id": str(campaign_id), **body.model_dump()},
        mutation=lambda: _pause_campaign_once(
            session=session,
            current_user=current_user,
            campaign_id=campaign_id,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _pause_campaign_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: str,
    body: PauseRequest,
) -> ControlStatePublic:
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
    request: Request,
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
) -> ControlStatePublic:
    """Resume campaign."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation=f"controls:campaign:{campaign_id}:resume",
        request_payload={"campaign_id": str(campaign_id)},
        mutation=lambda: _resume_campaign_once(
            session=session,
            current_user=current_user,
            campaign_id=campaign_id,
            workspace_id=workspace_id,
        ),
    )


def _resume_campaign_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: str,
) -> ControlStatePublic:
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
