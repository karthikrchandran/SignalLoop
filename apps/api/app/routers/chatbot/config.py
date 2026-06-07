"""ChatBot Hub configuration routes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.chatbot.prompts import validate_ai_disclosure
from app.domain.chatbot.repositories import (
    get_or_create_bot_config,
    list_channel_configs,
)
from app.domain.chatbot.retention import normalized_retention_days
from app.domain.chatbot.schemas import (
    ChatbotBusinessHoursConfig,
    ChatbotChannelPublic,
    ChatbotConfigPublic,
    ChatbotConfigUpdate,
    ChatbotLeadCaptureConfig,
)
from app.models import User
from app.routers.chatbot.router import (
    WorkspaceId,
    require_chatbot_admin,
    require_chatbot_agent,
)

router = APIRouter(prefix="/config", tags=["chatbot-config"])


def _channel_public(row) -> ChatbotChannelPublic:
    return ChatbotChannelPublic(
        id=row.id,
        workspace_id=row.workspace_id,
        channel_type=row.channel_type,
        display_name=row.display_name,
        status=row.status,
        is_active=row.is_active,
        has_credential=row.credential_id is not None,
        config_json=row.config_json,
        last_verified_at=row.last_verified_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _business_hours(raw: dict) -> ChatbotBusinessHoursConfig:
    return ChatbotBusinessHoursConfig(
        enabled=bool(raw.get("enabled", False)),
        timezone=str(raw.get("timezone") or "UTC"),
        days=[int(day) for day in raw.get("days", [0, 1, 2, 3, 4])],
        start=str(raw.get("start") or "09:00"),
        end=str(raw.get("end") or "17:00"),
    )


def _lead_capture(raw: dict) -> ChatbotLeadCaptureConfig:
    return ChatbotLeadCaptureConfig(
        enabled=bool(raw.get("enabled", True)),
        min_turns=int(raw.get("min_turns") or 3),
        intent_keywords=[str(item) for item in raw.get("intent_keywords", ["demo", "pricing", "buy"])],
        privacy_notice_text=raw.get("privacy_notice_text"),
        privacy_policy_url=raw.get("privacy_policy_url"),
        re_opt_in_invitation_enabled=bool(raw.get("re_opt_in_invitation_enabled", False)),
        confidence_threshold=float(raw.get("confidence_threshold", 0.25)),
    )


def _config_public(workspace_id: str, session) -> ChatbotConfigPublic:
    row = get_or_create_bot_config(workspace_id, session)
    return ChatbotConfigPublic(
        workspace_id=workspace_id,
        bot_name=row.bot_name,
        persona=row.persona,
        greeting_message=row.greeting_message,
        escalation_message=row.escalation_message,
        out_of_hours_message=row.out_of_hours_message,
        ai_disclosure=row.ai_disclosure,
        token_cap_per_session=row.token_cap_per_session,
        retention_days=row.retention_days,
        business_hours=_business_hours(row.business_hours_json or {}),
        lead_capture=_lead_capture(row.lead_capture_json or {}),
        reindex_schedule_time=str((row.business_hours_json or {}).get("reindex_schedule_time") or "02:00"),
        channel_overrides=[_channel_public(channel) for channel in list_channel_configs(workspace_id, session)],
        updated_at=row.updated_at,
    )


@router.get("", response_model=ChatbotConfigPublic)
def get_config(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotConfigPublic:
    """Return workspace bot behavior and compliance settings."""
    return _config_public(workspace_id, session)


@router.put("", response_model=ChatbotConfigPublic)
def update_config(
    body: ChatbotConfigUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotConfigPublic:
    """Update workspace bot behavior and compliance settings."""
    row = get_or_create_bot_config(workspace_id, session)
    if body.ai_disclosure is not None:
        try:
            row.ai_disclosure = validate_ai_disclosure(body.ai_disclosure)
        except AssertionError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if body.retention_days is not None:
        try:
            row.retention_days = normalized_retention_days(body.retention_days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    if body.token_cap_per_session is not None:
        row.token_cap_per_session = body.token_cap_per_session
    if body.bot_name is not None:
        row.bot_name = body.bot_name
    if body.persona is not None:
        row.persona = body.persona
    if body.greeting_message is not None:
        row.greeting_message = body.greeting_message
    if body.escalation_message is not None:
        row.escalation_message = body.escalation_message
    if body.out_of_hours_message is not None:
        row.out_of_hours_message = body.out_of_hours_message
    if body.business_hours is not None:
        business_hours = body.business_hours.model_dump()
        if body.reindex_schedule_time:
            business_hours["reindex_schedule_time"] = body.reindex_schedule_time
        row.business_hours_json = business_hours
    elif body.reindex_schedule_time:
        row.business_hours_json = {**(row.business_hours_json or {}), "reindex_schedule_time": body.reindex_schedule_time}
    if body.lead_capture is not None:
        row.lead_capture_json = body.lead_capture.model_dump()
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    append_audit_event_to_session(
        session,
        event_name="chatbot_config_updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="chatbot_config",
        resource_id=str(row.id),
        payload={
            "retention_days": row.retention_days,
            "token_cap_per_session": row.token_cap_per_session,
            "ai_disclosure_changed": body.ai_disclosure is not None,
            "lead_capture_changed": body.lead_capture is not None,
        },
    )
    session.commit()
    session.refresh(row)
    return _config_public(workspace_id, session)

