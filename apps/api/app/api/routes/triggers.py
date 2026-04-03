"""Trigger rule management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel

from app.domain.signals.trigger_service import get_trigger_rules, set_trigger_enabled
from app.infrastructure.authz.enforcer import require_role

router = APIRouter(prefix="/triggers", tags=["triggers"])


class TriggerUpdateRequest(SQLModel):
    enabled: bool


@router.get("/")
def list_triggers() -> list[dict]:
    return get_trigger_rules()


@router.put("/{signal_type}", dependencies=[Depends(require_role("operator"))])
def update_trigger(signal_type: str, body: TriggerUpdateRequest) -> dict[str, str]:
    if not set_trigger_enabled(signal_type, body.enabled):
        raise HTTPException(status_code=404, detail="Trigger rule not found")
    status = "enabled" if body.enabled else "disabled"
    return {"message": f"Trigger '{signal_type}' {status}"}
