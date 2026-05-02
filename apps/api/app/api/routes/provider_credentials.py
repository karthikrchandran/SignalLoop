"""API route: POST /workspaces/{workspace_id}/provider-credentials

Workspace admins use this endpoint to store provider API keys.
Keys are encrypted with Fernet (AES-128-CBC + HMAC) before being written to
the database.  The plaintext is never logged or returned to the caller.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.core.encryption import encrypt
from app.domain_models import NotificationProvider, ProviderCredential

router = APIRouter(
    prefix="/workspaces",
    tags=["provider-credentials"],
)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ProviderCredentialCreate(BaseModel):
    provider: NotificationProvider
    channel: str = Field(
        max_length=32,
        description="e.g. 'email', 'sms', 'voice', 'scheduling'",
    )
    api_key: str = Field(description="Provider API key — stored encrypted")
    api_secret: str | None = Field(
        default=None,
        description="Optional secondary secret (e.g. auth token, webhook secret)",
    )
    config_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra provider config (from_email, phone_number, …)",
    )


class ProviderCredentialPublic(BaseModel):
    id: uuid.UUID
    workspace_id: str
    provider: NotificationProvider
    channel: str
    has_api_secret: bool
    config_json: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class ProviderCredentialsPublic(BaseModel):
    data: list[ProviderCredentialPublic]
    count: int


def _ensure_workspace_path_matches_header(workspace_id: str, workspace_header: str) -> None:
    if workspace_id != workspace_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUTH_ERROR", "semantic": "AUTH_ERROR"}},
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/{workspace_id}/provider-credentials",
    response_model=ProviderCredentialPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Store provider credentials for a workspace",
)
def upsert_provider_credentials(
    *,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
    body: ProviderCredentialCreate,
) -> ProviderCredentialPublic:
    """Create or replace the active credential for a given provider+channel pair.

    The ``api_key`` (and optional ``api_secret``) are encrypted with Fernet
    before being persisted.  The response **never** includes the plaintext key.
    """
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    if not body.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key must not be empty",
        )

    # Deactivate any existing credential for this workspace+provider+channel
    existing = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == body.provider,
            ProviderCredential.channel == body.channel,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()
    for cred in existing:
        cred.is_active = False
        session.add(cred)

    cred = ProviderCredential(
        workspace_id=workspace_id,
        provider=body.provider,
        channel=body.channel,
        encrypted_api_key=encrypt(body.api_key),
        encrypted_api_secret=encrypt(body.api_secret) if body.api_secret else None,
        config_json=body.config_json,
        is_active=True,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)

    return ProviderCredentialPublic(
        id=cred.id,
        workspace_id=cred.workspace_id,
        provider=cred.provider,
        channel=cred.channel,
        has_api_secret=cred.encrypted_api_secret is not None,
        config_json=cred.config_json,
        is_active=cred.is_active,
    )


@router.get(
    "/{workspace_id}/provider-credentials",
    response_model=ProviderCredentialsPublic,
    dependencies=[Depends(require_admin)],
    summary="List active provider credentials for a workspace",
)
def list_provider_credentials(
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> ProviderCredentialsPublic:
    """Return metadata for all active credentials.  Plaintext keys are never exposed."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    rows = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).all()

    return ProviderCredentialsPublic(
        data=[
            ProviderCredentialPublic(
                id=r.id,
                workspace_id=r.workspace_id,
                provider=r.provider,
                channel=r.channel,
                has_api_secret=r.encrypted_api_secret is not None,
                config_json=r.config_json,
                is_active=r.is_active,
            )
            for r in rows
        ],
        count=len(rows),
    )


@router.delete(
    "/{workspace_id}/provider-credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
    summary="Deactivate a stored credential",
)
def deactivate_provider_credential(
    workspace_id: str,
    credential_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
    session: SessionDep,
) -> None:
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    cred = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == workspace_id,
        )
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    cred.is_active = False
    session.add(cred)
    session.commit()
