"""SignalLoop AI intelligence overview endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.engagement_intelligence.service import (
    EngagementOverviewPublic,
    build_engagement_overview,
)

router = APIRouter(
    prefix="/engagement-intelligence",
    tags=["engagement-intelligence"],
    dependencies=[Depends(require_admin)],
)


@router.get("/overview", response_model=EngagementOverviewPublic)
def get_engagement_overview(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> EngagementOverviewPublic:
    """Return next-best actions, unified work, journey, and recommendations."""
    return build_engagement_overview(session, workspace_id=workspace_id)
