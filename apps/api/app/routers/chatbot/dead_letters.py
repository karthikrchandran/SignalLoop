"""ChatBot Hub dead-letter operator routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.chatbot.schemas import (
    ChatbotDeadLetterRetryPublic,
    ChatbotDeadLettersPublic,
)
from app.domain.chatbot.webhook_ingestion import list_dead_letters, retry_dead_letter
from app.models import User
from app.routers.chatbot.router import (
    WorkspaceId,
    require_chatbot_operator,
)

router = APIRouter(prefix="/dead-letters", tags=["chatbot-dead-letters"])


def _redis_client(request: Request):
    manager = getattr(request.app.state, "redis_manager", None)
    redis = getattr(manager, "client", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Redis is not available")
    return redis


@router.get("", response_model=ChatbotDeadLettersPublic)
async def list_workspace_dead_letters(
    request: Request,
    workspace_id: WorkspaceId,
    _current_user: Annotated[User, Depends(require_chatbot_operator)],
) -> ChatbotDeadLettersPublic:
    """List dead-lettered chatbot messages for the active workspace."""
    rows = await list_dead_letters(_redis_client(request), workspace_id)
    return ChatbotDeadLettersPublic(data=rows, count=len(rows))


@router.post("/{dead_letter_id}/retry", response_model=ChatbotDeadLetterRetryPublic)
async def retry_workspace_dead_letter(
    dead_letter_id: str,
    request: Request,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_operator)],
) -> ChatbotDeadLetterRetryPublic:
    """Requeue a dead-lettered chatbot message."""
    try:
        record, queue_key = await retry_dead_letter(_redis_client(request), workspace_id, dead_letter_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dead-letter not found")

    append_audit_event_to_session(
        session,
        event_name="chatbot_dead_letter_retried",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_dead_letter",
        resource_id=dead_letter_id,
        payload={
            "provider_message_id": record.get("provider_message_id"),
            "channel_type": record.get("channel_type"),
            "attempt_count": record.get("attempt_count"),
        },
    )
    session.commit()
    return ChatbotDeadLetterRetryPublic(id=dead_letter_id, requeued=True, inbound_queue_key=queue_key)
