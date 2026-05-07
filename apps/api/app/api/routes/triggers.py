"""Trigger rule management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel

from app.api.deps import CurrentUser, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.audit.audit_events import append_audit_event, audit_actor_role
from app.domain.signals.trigger_service import get_trigger_rules, set_trigger_enabled

router = APIRouter(prefix="/triggers", tags=["triggers"], dependencies=[Depends(require_admin)])


class TriggerUpdateRequest(SQLModel):
    """Request payload: trigger update."""
    enabled: bool


@router.get("/")
def list_triggers() -> list[dict]:
    """Return a list of triggers."""
    return get_trigger_rules()


@router.put("/{signal_type}")
async def update_trigger(
    signal_type: str,
    body: TriggerUpdateRequest,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    """Update trigger."""
    if not set_trigger_enabled(signal_type, body.enabled):
        raise HTTPException(status_code=404, detail="Trigger rule not found")
    status = "enabled" if body.enabled else "disabled"
    await append_audit_event(
        event_name="trigger.rule_updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="trigger_rule",
        resource_id=signal_type,
        payload={"signal_type": signal_type, "enabled": body.enabled},
    )
    return {"message": f"Trigger '{signal_type}' {status}"}
