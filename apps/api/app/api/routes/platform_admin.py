"""Platform-only control-plane endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.tenants.models import SupportAccessGrant, Tenant, utc_now
from app.models import User

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])


class SupportGrantCreate(BaseModel):
    tenant_id: uuid.UUID
    operator_user_id: uuid.UUID
    capabilities: list[str] = Field(min_length=1)
    reason: str = Field(min_length=3, max_length=500)
    ticket_reference: str | None = Field(default=None, max_length=255)
    expires_at: datetime


def _require_platform_admin(user: CurrentUser) -> None:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administration is required",
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.post(
    "/support-grants",
    response_model=SupportAccessGrant,
    status_code=status.HTTP_201_CREATED,
)
def issue_support_grant(
    *,
    session: SessionDep,
    user: CurrentUser,
    payload: SupportGrantCreate,
) -> SupportAccessGrant:
    """Issue an approved, reasoned, short-lived tenant support grant."""
    _require_platform_admin(user)
    if session.get(Tenant, payload.tenant_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if session.get(User, payload.operator_user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    if _as_utc(payload.expires_at) <= utc_now():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Grant expiry must be in the future",
        )

    grant = SupportAccessGrant(
        tenant_id=payload.tenant_id,
        operator_user_id=payload.operator_user_id,
        capabilities=sorted(set(payload.capabilities)),
        reason=payload.reason,
        ticket_reference=payload.ticket_reference,
        approved_by=user.id,
        expires_at=_as_utc(payload.expires_at),
    )
    session.add(grant)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="support.grant.issued",
        workspace_id=str(grant.tenant_id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="support_grant",
        resource_id=str(grant.id),
        payload={"capabilities": grant.capabilities, "ticket_reference": grant.ticket_reference},
    )
    session.commit()
    session.refresh(grant)
    return grant


@router.post("/support-grants/{grant_id}/revoke", response_model=SupportAccessGrant)
def revoke_support_grant(
    *, session: SessionDep, user: CurrentUser, grant_id: uuid.UUID
) -> SupportAccessGrant:
    """Revoke a grant once; repeated requests retain the original revocation time."""
    _require_platform_admin(user)
    grant = session.get(SupportAccessGrant, grant_id)
    if grant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Support grant not found",
        )
    if grant.revoked_at is None:
        grant.revoked_at = utc_now()
        session.add(grant)
        append_audit_event_to_session(
            session,
            event_name="support.grant.revoked",
            workspace_id=str(grant.tenant_id),
            actor_id=user.id,
            actor_role=audit_actor_role(user),
            resource_type="support_grant",
            resource_id=str(grant.id),
        )
        session.commit()
        session.refresh(grant)
    return grant
