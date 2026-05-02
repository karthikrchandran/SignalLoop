"""Campaign dashboard metrics endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.dashboard import service as dashboard_service
from app.domain_models import Campaign

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


def _ensure_campaign_in_workspace(
    session: SessionDep,
    campaign_id: uuid.UUID,
    workspace_id: str,
) -> None:
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")


@router.get("/campaigns/{campaign_id}/email-metrics")
def get_email_metrics(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID,
) -> dict:
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    return dashboard_service.get_email_metrics(session, campaign_id)


@router.get("/campaigns/{campaign_id}/call-metrics")
def get_call_metrics(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID,
) -> dict:
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    return dashboard_service.get_call_metrics(session, campaign_id)


@router.get("/campaigns/{campaign_id}/signals")
def get_signal_summary(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID,
) -> dict:
    _ensure_campaign_in_workspace(session, campaign_id, workspace_id)
    return dashboard_service.get_signal_summary(session, campaign_id)


@router.get("/daily-cap-status")
def get_daily_cap_status(session: SessionDep, workspace_id: WorkspaceIdDep) -> dict:
    return dashboard_service.get_daily_cap_status(session, workspace_id=workspace_id)
