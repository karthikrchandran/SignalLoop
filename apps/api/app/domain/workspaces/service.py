"""Workspace membership service functions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.domain.workspaces.models import Workspace, WorkspaceMembership

WORKSPACE_ROLE_OWNER = "owner"
WORKSPACE_ROLE_SUPER_ADMIN = "super_admin"
WORKSPACE_ROLE_ADMIN = "admin"
WORKSPACE_ROLE_AGENT = "agent"
WORKSPACE_ROLE_SUPPORT_AGENT = "support_agent"
WORKSPACE_ROLE_OPERATOR = "operator"
WORKSPACE_STATUS_ACTIVE = "active"
WORKSPACE_STATUS_INACTIVE = "inactive"

WORKSPACE_MEMBER_ROLES = {
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_SUPER_ADMIN,
    WORKSPACE_ROLE_ADMIN,
    WORKSPACE_ROLE_AGENT,
    WORKSPACE_ROLE_SUPPORT_AGENT,
    WORKSPACE_ROLE_OPERATOR,
}
WORKSPACE_ADMIN_ROLES = {
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_SUPER_ADMIN,
    WORKSPACE_ROLE_ADMIN,
}
WORKSPACE_AGENT_ROLES = {
    *WORKSPACE_ADMIN_ROLES,
    WORKSPACE_ROLE_AGENT,
    WORKSPACE_ROLE_SUPPORT_AGENT,
    WORKSPACE_ROLE_OPERATOR,
}
WORKSPACE_OPERATOR_ROLES = {
    WORKSPACE_ROLE_OWNER,
    WORKSPACE_ROLE_SUPER_ADMIN,
    WORKSPACE_ROLE_OPERATOR,
}
WORKSPACE_MEMBERSHIP_STATUSES = {WORKSPACE_STATUS_ACTIVE, WORKSPACE_STATUS_INACTIVE}


def normalize_workspace_id(workspace_id: str) -> str:
    """Normalize a workspace id supplied by clients or seed code."""
    return workspace_id.strip()


def role_for_user(user: Any) -> str:
    """Return the default workspace role for a user-like object."""
    if getattr(user, "is_superuser", False):
        return WORKSPACE_ROLE_SUPER_ADMIN
    role = getattr(user, "role", None)
    return str(role or WORKSPACE_ROLE_OPERATOR)


def get_workspace(session: Session, workspace_id: str) -> Workspace | None:
    """Return a workspace by id."""
    return session.get(Workspace, normalize_workspace_id(workspace_id))


def ensure_workspace(
    session: Session,
    workspace_id: str,
    *,
    display_name: str | None = None,
) -> Workspace:
    """Create a workspace if it does not already exist."""
    normalized = normalize_workspace_id(workspace_id)
    workspace = session.get(Workspace, normalized)
    if workspace:
        return workspace
    workspace = Workspace(id=normalized, display_name=display_name or normalized)
    session.add(workspace)
    session.flush()
    return workspace


def get_active_membership(
    session: Session,
    *,
    user_id: uuid.UUID,
    workspace_id: str,
) -> WorkspaceMembership | None:
    """Return a user's active membership for a workspace."""
    return session.exec(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == normalize_workspace_id(workspace_id),
            WorkspaceMembership.status == WORKSPACE_STATUS_ACTIVE,
        )
    ).first()


def ensure_workspace_membership(
    session: Session,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
    role: str = WORKSPACE_ROLE_OPERATOR,
    status: str = WORKSPACE_STATUS_ACTIVE,
) -> WorkspaceMembership:
    """Create or update a user's membership in a workspace."""
    workspace = ensure_workspace(session, workspace_id)
    membership = session.exec(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace.id,
            WorkspaceMembership.user_id == user_id,
        )
    ).first()
    if membership:
        changed = False
        if membership.role != role:
            membership.role = role
            changed = True
        if membership.status != status:
            membership.status = status
            changed = True
        if changed:
            membership.updated_at = datetime.now(timezone.utc)
            session.add(membership)
            session.flush()
        return membership

    membership = WorkspaceMembership(
        workspace_id=workspace.id,
        user_id=user_id,
        role=role,
        status=status,
    )
    session.add(membership)
    session.flush()
    return membership


def user_has_workspace_access(
    session: Session,
    *,
    user: Any,
    workspace_id: str,
    allowed_roles: set[str] | None = None,
) -> bool:
    """Return whether a user can access a workspace, optionally by role."""
    if getattr(user, "is_superuser", False):
        return True
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False
    membership = get_active_membership(
        session,
        user_id=user_id,
        workspace_id=workspace_id,
    )
    if membership is None:
        return False
    return allowed_roles is None or membership.role in allowed_roles
