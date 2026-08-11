"""Tenant-bound support grant resolution and audit logging."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.tenants.models import SupportAccessGrant


class SupportAccessDenied(PermissionError):
    """A support grant cannot be used for the requested tenant capability."""


@dataclass(frozen=True)
class SupportAccessContext:
    grant_id: uuid.UUID
    tenant_id: uuid.UUID
    operator_user_id: uuid.UUID
    capability: str


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _deny(
    session: Session,
    *,
    grant_id: uuid.UUID,
    tenant_id: uuid.UUID,
    operator_user_id: uuid.UUID,
    capability: str,
    reason: str,
) -> None:
    append_audit_event_to_session(
        session,
        event_name="support.grant.denied",
        workspace_id=str(tenant_id),
        actor_id=operator_user_id,
        actor_role="platform_support",
        resource_type="support_grant",
        resource_id=str(grant_id),
        payload={"capability": capability, "denial_reason": reason},
    )
    raise SupportAccessDenied(reason)


def resolve_support_context(
    session: Session,
    *,
    grant_id: uuid.UUID,
    operator_user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    required_capability: str,
    now: datetime | None = None,
) -> SupportAccessContext:
    """Resolve one approved, live grant without trusting request-supplied authority."""
    grant = session.get(SupportAccessGrant, grant_id)
    if grant is None:
        _deny(
            session,
            grant_id=grant_id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_NOT_FOUND",
        )

    assert grant is not None
    current_time = _as_utc(now or datetime.now(timezone.utc))
    if grant.tenant_id != tenant_id:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_TENANT_MISMATCH",
        )
    if grant.operator_user_id != operator_user_id:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_OPERATOR_MISMATCH",
        )
    if grant.approved_by is None:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_NOT_APPROVED",
        )
    if grant.revoked_at is not None:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_REVOKED",
        )
    if _as_utc(grant.starts_at) > current_time:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_NOT_STARTED",
        )
    if _as_utc(grant.expires_at) <= current_time:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_EXPIRED",
        )
    if required_capability not in grant.capabilities:
        _deny(
            session,
            grant_id=grant.id,
            tenant_id=tenant_id,
            operator_user_id=operator_user_id,
            capability=required_capability,
            reason="SUPPORT_GRANT_CAPABILITY_DENIED",
        )

    append_audit_event_to_session(
        session,
        event_name="support.grant.used",
        workspace_id=str(tenant_id),
        actor_id=operator_user_id,
        actor_role="platform_support",
        resource_type="support_grant",
        resource_id=str(grant.id),
        payload={"capability": required_capability},
    )
    return SupportAccessContext(
        grant_id=grant.id,
        tenant_id=grant.tenant_id,
        operator_user_id=grant.operator_user_id,
        capability=required_capability,
    )
