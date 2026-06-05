"""Workspace runtime-config endpoints for non-provider settings."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.core.encryption import encrypt
from app.domain.runtime_settings import resolve_workspace_runtime_config
from app.domain_models import WorkspaceRuntimeConfig

router = APIRouter(prefix="/workspaces", tags=["workspace-runtime-config"])


class WorkspaceRuntimeConfigUpsert(BaseModel):
    """Request payload for creating or updating runtime settings."""

    deepgram_api_key: str | None = Field(default=None)
    groq_api_key: str | None = Field(default=None)
    team_notification_email: EmailStr | None = Field(default=None)


class WorkspaceRuntimeConfigPublic(BaseModel):
    """Public API response for runtime settings metadata."""

    workspace_id: str
    deepgram_configured: bool
    groq_configured: bool
    team_notification_email: str | None = None
    sources: dict[str, str]
    updated_at: datetime | None = None


def _ensure_workspace_path_matches_header(workspace_id: str, workspace_header: str) -> None:
    if workspace_id != workspace_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUTH_ERROR", "semantic": "AUTH_ERROR"}},
        )


def _serialize_runtime_config(
    session: SessionDep,
    workspace_id: str,
    row: WorkspaceRuntimeConfig | None = None,
) -> WorkspaceRuntimeConfigPublic:
    resolved = resolve_workspace_runtime_config(session, workspace_id)
    return WorkspaceRuntimeConfigPublic(
        workspace_id=workspace_id,
        deepgram_configured=resolved.deepgram_api_key.configured,
        groq_configured=resolved.groq_api_key.configured,
        team_notification_email=resolved.team_notification_email.value or None,
        sources={
            "deepgram": resolved.deepgram_api_key.source,
            "groq": resolved.groq_api_key.source,
            "team_notifications": resolved.team_notification_email.source,
        },
        updated_at=row.updated_at if row else None,
    )


@router.get(
    "/{workspace_id}/runtime-config",
    response_model=WorkspaceRuntimeConfigPublic,
    dependencies=[Depends(require_admin)],
)
def get_workspace_runtime_config(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> WorkspaceRuntimeConfigPublic:
    """Return effective runtime-setting metadata for a workspace."""

    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    row = session.exec(
        select(WorkspaceRuntimeConfig).where(WorkspaceRuntimeConfig.workspace_id == workspace_id)
    ).first()
    return _serialize_runtime_config(session, workspace_id, row)


@router.post(
    "/{workspace_id}/runtime-config",
    response_model=WorkspaceRuntimeConfigPublic,
    dependencies=[Depends(require_admin)],
)
def upsert_workspace_runtime_config(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
    body: WorkspaceRuntimeConfigUpsert,
) -> WorkspaceRuntimeConfigPublic:
    """Create or update runtime-setting overrides for a workspace."""

    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    row = session.exec(
        select(WorkspaceRuntimeConfig).where(WorkspaceRuntimeConfig.workspace_id == workspace_id)
    ).first()
    if row is None:
        row = WorkspaceRuntimeConfig(workspace_id=workspace_id)

    provided_fields = body.model_fields_set
    if not provided_fields:
        raise HTTPException(status_code=422, detail="At least one field must be provided")

    if "deepgram_api_key" in provided_fields:
        deepgram_value = (body.deepgram_api_key or "").strip()
        row.encrypted_deepgram_api_key = encrypt(deepgram_value) if deepgram_value else None

    if "groq_api_key" in provided_fields:
        groq_value = (body.groq_api_key or "").strip()
        row.encrypted_groq_api_key = encrypt(groq_value) if groq_value else None

    if "team_notification_email" in provided_fields:
        row.team_notification_email = (
            str(body.team_notification_email).strip() if body.team_notification_email else None
        )

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_runtime_config(session, workspace_id, row)