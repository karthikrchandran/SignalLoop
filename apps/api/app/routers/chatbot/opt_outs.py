"""ChatBot Hub opt-out management routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.chatbot.models import ChatbotOptOut
from app.domain.chatbot.schemas import (
    ChatbotOptOutDeletePublic,
    ChatbotOptOutPublic,
    ChatbotOptOutsPublic,
)
from app.models import User
from app.routers.chatbot.router import WorkspaceId, require_chatbot_admin

router = APIRouter(prefix="/opt-outs", tags=["chatbot-opt-outs"])


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _public(row: ChatbotOptOut) -> ChatbotOptOutPublic:
    return ChatbotOptOutPublic(
        id=row.id,
        workspace_id=row.workspace_id,
        channel_type=row.channel_type,
        visitor_id=row.visitor_id,
        contact_id=row.contact_id,
        reason=row.reason,
        actor="visitor",
        created_at=row.created_at,
        reopt_in_invited_at=row.reopt_in_invited_at,
    )


@router.get("", response_model=ChatbotOptOutsPublic)
def list_opt_out_rows(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotOptOutsPublic:
    """Return active opt-outs for the workspace."""
    rows = list(
        session.exec(
            select(ChatbotOptOut)
            .where(
                ChatbotOptOut.workspace_id == workspace_id,
                ChatbotOptOut.reopt_in_invited_at.is_(None),
            )
            .order_by(col(ChatbotOptOut.created_at).desc())
        ).all()
    )
    return ChatbotOptOutsPublic(data=[_public(row) for row in rows], count=len(rows))


@router.delete("/{opt_out_id}", response_model=ChatbotOptOutDeletePublic)
def remove_opt_out(
    opt_out_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotOptOutDeletePublic:
    """Admin re-enables chatbot automation for one opted-out visitor."""
    row = session.exec(
        select(ChatbotOptOut).where(
            ChatbotOptOut.workspace_id == workspace_id,
            ChatbotOptOut.id == opt_out_id,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Opt-out not found")
    row.reopt_in_invited_at = row.reopt_in_invited_at or datetime.now(timezone.utc)
    append_audit_event_to_session(
        session,
        event_name="chatbot_opt_out_removed",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_opt_out",
        resource_id=str(row.id),
        payload={
            "channel_type": _enum_value(row.channel_type),
            "visitor_id": row.visitor_id,
            "reopt_in_invited_at": row.reopt_in_invited_at.isoformat(),
        },
    )
    session.add(row)
    session.commit()
    return ChatbotOptOutDeletePublic(id=opt_out_id, removed=True)
