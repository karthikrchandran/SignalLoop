"""ChatBot Hub channel setup routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.encryption import encrypt
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.chatbot.channel_readiness import build_channel_readiness
from app.domain.chatbot.models import (
    ChatbotChannelConfig,
    ChatbotChannelStatus,
)
from app.domain.chatbot.repositories import (
    get_channel_config_by_id,
    list_channel_configs,
)
from app.domain.chatbot.schemas import (
    ChatbotChannelCreate,
    ChatbotChannelPublic,
    ChatbotChannelsPublic,
    ChatbotChannelToggle,
    ChatbotChannelUpdate,
)
from app.domain_models import ProviderCredential
from app.infrastructure.providers.chat.registry import provider_for_channel
from app.models import User
from app.routers.chatbot.router import (
    WorkspaceId,
    require_chatbot_admin,
    require_chatbot_agent,
)

router = APIRouter(prefix="/channels", tags=["chatbot-channels"])


def _mask_channel(row: ChatbotChannelConfig) -> ChatbotChannelPublic:
    return ChatbotChannelPublic(
        id=row.id,
        workspace_id=row.workspace_id,
        channel_type=row.channel_type,
        display_name=row.display_name,
        status=row.status,
        is_active=row.is_active,
        has_credential=row.credential_id is not None,
        config_json=row.config_json,
        readiness=build_channel_readiness(row),
        last_verified_at=row.last_verified_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _audit(
    session,
    *,
    event_name: str,
    workspace_id: str,
    current_user: User,
    channel: ChatbotChannelConfig,
) -> None:
    append_audit_event_to_session(
        session,
        event_name=event_name,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_channel",
        resource_id=str(channel.id),
        payload={
            "channel_id": str(channel.id),
            "channel_type": channel.channel_type.value,
            "status": channel.status.value,
            "is_active": channel.is_active,
        },
    )


def _upsert_credential(
    session,
    *,
    workspace_id: str,
    body: ChatbotChannelCreate | ChatbotChannelUpdate,
    existing: ChatbotChannelConfig | None,
) -> uuid.UUID | None:
    if body.credentials is None:
        return existing.credential_id if existing else None

    channel_type = body.channel_type if isinstance(body, ChatbotChannelCreate) else existing.channel_type
    provider = provider_for_channel(channel_type)
    if existing and existing.credential_id:
        previous = session.get(ProviderCredential, existing.credential_id)
        if previous:
            previous.is_active = False
            session.add(previous)

    config_json = dict(body.config_json or (existing.config_json if existing else {}))
    if body.credentials.webhook_secret:
        config_json["webhook_secret_present"] = True

    credential = ProviderCredential(
        workspace_id=workspace_id,
        provider=provider,
        channel="chatbot",
        encrypted_api_key=encrypt(body.credentials.api_key),
        encrypted_api_secret=(
            encrypt(body.credentials.webhook_secret or body.credentials.api_secret)
            if body.credentials.webhook_secret or body.credentials.api_secret
            else None
        ),
        config_json=config_json,
        is_active=True,
    )
    session.add(credential)
    session.flush()
    return credential.id


@router.get("", response_model=ChatbotChannelsPublic)
def list_channels(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotChannelsPublic:
    """List chatbot channels for the active workspace."""
    rows = list_channel_configs(workspace_id, session)
    return ChatbotChannelsPublic(data=[_mask_channel(row) for row in rows], count=len(rows))


@router.post("", response_model=ChatbotChannelPublic, status_code=status.HTTP_201_CREATED)
def create_channel(
    body: ChatbotChannelCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotChannelPublic:
    """Create or replace a chatbot channel config."""
    existing = session.exec(
        select(ChatbotChannelConfig).where(
            ChatbotChannelConfig.workspace_id == workspace_id,
            ChatbotChannelConfig.channel_type == body.channel_type,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Channel already exists")

    channel = ChatbotChannelConfig(
        workspace_id=workspace_id,
        channel_type=body.channel_type,
        display_name=body.display_name,
        status=ChatbotChannelStatus.connected if body.is_active else ChatbotChannelStatus.draft,
        is_active=body.is_active,
        config_json=body.config_json,
    )
    session.add(channel)
    session.flush()
    channel.credential_id = _upsert_credential(session, workspace_id=workspace_id, body=body, existing=channel)
    channel.updated_at = datetime.now(timezone.utc)
    session.add(channel)
    _audit(session, event_name="chatbot_channel_created", workspace_id=workspace_id, current_user=current_user, channel=channel)
    session.commit()
    session.refresh(channel)
    return _mask_channel(channel)


@router.get("/{channel_id}", response_model=ChatbotChannelPublic)
def get_channel(
    channel_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotChannelPublic:
    """Read one chatbot channel config without leaking cross-workspace metadata."""
    row = get_channel_config_by_id(workspace_id, session, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _mask_channel(row)


@router.put("/{channel_id}", response_model=ChatbotChannelPublic)
def update_channel(
    channel_id: uuid.UUID,
    body: ChatbotChannelUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotChannelPublic:
    """Update one chatbot channel config."""
    row = get_channel_config_by_id(workspace_id, session, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")

    if body.display_name is not None:
        row.display_name = body.display_name
    if body.config_json is not None:
        row.config_json = body.config_json
    if body.is_active is not None:
        row.is_active = body.is_active
        row.status = ChatbotChannelStatus.connected if body.is_active else ChatbotChannelStatus.disabled
    row.credential_id = _upsert_credential(session, workspace_id=workspace_id, body=body, existing=row)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    _audit(session, event_name="chatbot_channel_updated", workspace_id=workspace_id, current_user=current_user, channel=row)
    session.commit()
    session.refresh(row)
    return _mask_channel(row)


@router.patch("/{channel_id}/toggle", response_model=ChatbotChannelPublic)
def toggle_channel(
    channel_id: uuid.UUID,
    body: ChatbotChannelToggle,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotChannelPublic:
    """Activate or deactivate a chatbot channel."""
    row = get_channel_config_by_id(workspace_id, session, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    row.is_active = body.is_active
    row.status = ChatbotChannelStatus.connected if body.is_active else ChatbotChannelStatus.disabled
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    _audit(session, event_name="chatbot_channel_toggled", workspace_id=workspace_id, current_user=current_user, channel=row)
    session.commit()
    session.refresh(row)
    return _mask_channel(row)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> None:
    """Delete a chatbot channel and deactivate its credential."""
    row = get_channel_config_by_id(workspace_id, session, channel_id)
    if not row:
        raise HTTPException(status_code=404, detail="Channel not found")
    if row.credential_id:
        credential = session.get(ProviderCredential, row.credential_id)
        if credential:
            credential.is_active = False
            session.add(credential)
    _audit(session, event_name="chatbot_channel_deleted", workspace_id=workspace_id, current_user=current_user, channel=row)
    session.delete(row)
    session.commit()
