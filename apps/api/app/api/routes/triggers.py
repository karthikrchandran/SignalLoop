"""Trigger rule management API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import SQLModel

from app.api.deps import require_admin
from app.domain.signals.trigger_service import get_trigger_rules, set_trigger_enabled

router = APIRouter(prefix="/triggers", tags=["triggers"], dependencies=[Depends(require_admin)])


class TriggerUpdateRequest(SQLModel):
    enabled: bool


@router.get("/")
def list_triggers() -> list[dict]:
    return get_trigger_rules()


@router.put("/{signal_type}")
def update_trigger(signal_type: str, body: TriggerUpdateRequest) -> dict[str, str]:
    if not set_trigger_enabled(signal_type, body.enabled):
        raise HTTPException(status_code=404, detail="Trigger rule not found")
    status = "enabled" if body.enabled else "disabled"
    return {"message": f"Trigger '{signal_type}' {status}"}
