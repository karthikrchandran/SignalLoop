"""Workspace and workspace-membership administration endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.api.request_context import WorkspaceIdDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.workspaces.models import Workspace, WorkspaceMembership
from app.domain.workspaces.service import (
    WORKSPACE_ADMIN_ROLES,
    WORKSPACE_MEMBER_ROLES,
    WORKSPACE_MEMBERSHIP_STATUSES,
    WORKSPACE_STATUS_ACTIVE,
    WORKSPACE_STATUS_INACTIVE,
    ensure_workspace,
    ensure_workspace_membership,
    normalize_workspace_id,
)
from app.models import User

router = APIRouter(tags=["workspaces"])

WorkspaceRole = Literal[
    "owner",
    "super_admin",
    "admin",
    "agent",
    "support_agent",
    "operator",
]
MembershipStatus = Literal["active", "inactive"]
MembershipStatusFilter = Literal["active", "inactive", "all"]


class WorkspaceCreate(BaseModel):
    """Request payload for creating a workspace."""

    id: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)


class WorkspaceUpdate(BaseModel):
    """Request payload for updating workspace metadata."""

    display_name: str = Field(min_length=1, max_length=255)


class WorkspacePublic(BaseModel):
    """Public workspace response."""

    id: str
    display_name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkspacesPublic(BaseModel):
    """Workspace collection response."""

    data: list[WorkspacePublic]
    count: int


class WorkspaceMemberPut(BaseModel):
    """Request payload for creating or replacing a workspace membership."""

    role: WorkspaceRole = "operator"


class WorkspaceMemberPatch(BaseModel):
    """Request payload for partially updating a workspace membership."""

    role: WorkspaceRole | None = None
    status: MembershipStatus | None = None


class WorkspaceMemberPublic(BaseModel):
    """Public workspace membership response."""

    id: uuid.UUID
    workspace_id: str
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class WorkspaceMembersPublic(BaseModel):
    """Workspace membership collection response."""

    data: list[WorkspaceMemberPublic]
    count: int


def _workspace_admin_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "semantic": "POLICY_VIOLATION" if status_code == status.HTTP_409_CONFLICT else "AUTH_ERROR",
                "details": {},
            }
        },
    )


def _ensure_workspace_path_matches_header(workspace_id: str, workspace_header: str) -> None:
    if normalize_workspace_id(workspace_id) != workspace_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "AUTH_ERROR", "semantic": "AUTH_ERROR"}},
        )


def _workspace_or_404(session: SessionDep, workspace_id: str) -> Workspace:
    workspace = session.get(Workspace, normalize_workspace_id(workspace_id))
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return workspace


def _user_or_404(session: SessionDep, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _membership_or_404(
    session: SessionDep,
    *,
    workspace_id: str,
    user_id: uuid.UUID,
) -> WorkspaceMembership:
    membership = session.exec(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == normalize_workspace_id(workspace_id),
            WorkspaceMembership.user_id == user_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace member not found")
    return membership


def _active_admin_count(
    session: SessionDep,
    workspace_id: str,
    *,
    exclude_user_id: uuid.UUID | None = None,
) -> int:
    query = select(WorkspaceMembership).where(
        WorkspaceMembership.workspace_id == normalize_workspace_id(workspace_id),
        WorkspaceMembership.status == WORKSPACE_STATUS_ACTIVE,
        WorkspaceMembership.role.in_(WORKSPACE_ADMIN_ROLES),  # type: ignore[attr-defined]
    )
    if exclude_user_id is not None:
        query = query.where(WorkspaceMembership.user_id != exclude_user_id)
    return len(session.exec(query).all())


def _prevent_last_admin_removal(
    session: SessionDep,
    membership: WorkspaceMembership,
    *,
    next_role: str,
    next_status: str,
) -> None:
    is_current_admin = (
        membership.status == WORKSPACE_STATUS_ACTIVE
        and membership.role in WORKSPACE_ADMIN_ROLES
    )
    is_next_admin = (
        next_status == WORKSPACE_STATUS_ACTIVE and next_role in WORKSPACE_ADMIN_ROLES
    )
    if (
        is_current_admin
        and not is_next_admin
        and _active_admin_count(
            session,
            membership.workspace_id,
            exclude_user_id=membership.user_id,
        )
        == 0
    ):
        raise _workspace_admin_error(
            "LAST_WORKSPACE_ADMIN",
            "At least one active workspace admin is required",
            status.HTTP_409_CONFLICT,
        )


def _serialize_member(member: WorkspaceMembership, user: User) -> WorkspaceMemberPublic:
    return WorkspaceMemberPublic(
        id=member.id,
        workspace_id=member.workspace_id,
        user_id=member.user_id,
        email=str(user.email),
        full_name=user.full_name,
        role=member.role,
        status=member.status,
        created_at=member.created_at,
        updated_at=member.updated_at,
    )


def _audit(
    session: SessionDep,
    *,
    event_name: str,
    workspace_id: str,
    current_user: User,
    payload: dict,
) -> None:
    append_audit_event_to_session(
        session,
        event_name=event_name,
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="workspace",
        resource_id=workspace_id,
        payload=payload,
    )


@router.get("/", response_model=WorkspacesPublic)
def list_workspaces(session: SessionDep, current_user: CurrentUser) -> WorkspacesPublic:
    """List workspaces visible to the current user."""
    if current_user.is_superuser:
        workspaces = session.exec(select(Workspace).order_by(Workspace.id)).all()
    else:
        workspaces = session.exec(
            select(Workspace)
            .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
            .where(
                WorkspaceMembership.user_id == current_user.id,
                WorkspaceMembership.status == WORKSPACE_STATUS_ACTIVE,
            )
            .order_by(Workspace.id)
        ).all()
    return WorkspacesPublic(data=list(workspaces), count=len(workspaces))


@router.post(
    "/",
    response_model=WorkspacePublic,
    status_code=status.HTTP_201_CREATED,
)
def create_workspace(
    *,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_active_superuser)],
    body: WorkspaceCreate,
) -> WorkspacePublic:
    """Create a workspace and make the platform superuser an owner."""
    workspace_id = normalize_workspace_id(body.id)
    display_name = body.display_name.strip()
    if session.get(Workspace, workspace_id):
        raise _workspace_admin_error(
            "WORKSPACE_ALREADY_EXISTS",
            "Workspace already exists",
            status.HTTP_409_CONFLICT,
        )

    workspace = ensure_workspace(session, workspace_id, display_name=display_name)
    ensure_workspace_membership(
        session,
        workspace_id=workspace.id,
        user_id=current_user.id,
        role="owner",
    )
    _audit(
        session,
        event_name="workspace.created",
        workspace_id=workspace.id,
        current_user=current_user,
        payload={"workspace_id": workspace.id, "display_name": workspace.display_name},
    )
    session.commit()
    session.refresh(workspace)
    return WorkspacePublic.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspacePublic)
def get_workspace(
    *,
    session: SessionDep,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
) -> WorkspacePublic:
    """Return one workspace."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    return WorkspacePublic.model_validate(_workspace_or_404(session, workspace_id))


@router.patch("/{workspace_id}", response_model=WorkspacePublic)
def update_workspace(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    body: WorkspaceUpdate,
) -> WorkspacePublic:
    """Update workspace metadata."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    workspace = _workspace_or_404(session, workspace_id)
    workspace.display_name = body.display_name.strip()
    workspace.updated_at = datetime.now(timezone.utc)
    session.add(workspace)
    _audit(
        session,
        event_name="workspace.updated",
        workspace_id=workspace.id,
        current_user=current_user,
        payload={"workspace_id": workspace.id, "display_name": workspace.display_name},
    )
    session.commit()
    session.refresh(workspace)
    return WorkspacePublic.model_validate(workspace)


@router.get("/{workspace_id}/members", response_model=WorkspaceMembersPublic)
def list_workspace_members(
    *,
    session: SessionDep,
    workspace_id: str,
    workspace_header: WorkspaceIdDep,
    status_filter: Annotated[MembershipStatusFilter, Query(alias="status")] = "active",
) -> WorkspaceMembersPublic:
    """List workspace members."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    _workspace_or_404(session, workspace_id)

    query = (
        select(WorkspaceMembership, User)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(WorkspaceMembership.workspace_id == normalize_workspace_id(workspace_id))
        .order_by(WorkspaceMembership.created_at.desc())
    )
    if status_filter != "all":
        query = query.where(WorkspaceMembership.status == status_filter)
    rows = session.exec(query).all()
    data = [_serialize_member(member, user) for member, user in rows]
    return WorkspaceMembersPublic(data=data, count=len(data))


@router.put(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberPublic,
)
def put_workspace_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    user_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
    body: WorkspaceMemberPut,
) -> WorkspaceMemberPublic:
    """Create or replace a workspace membership for an existing user."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    _workspace_or_404(session, workspace_id)
    user = _user_or_404(session, user_id)

    existing = session.exec(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == normalize_workspace_id(workspace_id),
            WorkspaceMembership.user_id == user_id,
        )
    ).first()
    if existing:
        _prevent_last_admin_removal(
            session,
            existing,
            next_role=body.role,
            next_status=WORKSPACE_STATUS_ACTIVE,
        )

    member = ensure_workspace_membership(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        role=body.role,
        status=WORKSPACE_STATUS_ACTIVE,
    )
    _audit(
        session,
        event_name="workspace.member_upserted",
        workspace_id=normalize_workspace_id(workspace_id),
        current_user=current_user,
        payload={"user_id": str(user_id), "role": member.role, "status": member.status},
    )
    session.commit()
    session.refresh(member)
    return _serialize_member(member, user)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberPublic,
)
def patch_workspace_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    user_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
    body: WorkspaceMemberPatch,
) -> WorkspaceMemberPublic:
    """Partially update a workspace membership."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    _workspace_or_404(session, workspace_id)
    user = _user_or_404(session, user_id)
    member = _membership_or_404(session, workspace_id=workspace_id, user_id=user_id)
    if not body.model_fields_set:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="At least one field must be provided")

    next_role = body.role or member.role
    next_status = body.status or member.status
    if next_role not in WORKSPACE_MEMBER_ROLES or next_status not in WORKSPACE_MEMBERSHIP_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid membership role or status")
    _prevent_last_admin_removal(
        session,
        member,
        next_role=next_role,
        next_status=next_status,
    )
    member.role = next_role
    member.status = next_status
    member.updated_at = datetime.now(timezone.utc)
    session.add(member)
    _audit(
        session,
        event_name="workspace.member_updated",
        workspace_id=member.workspace_id,
        current_user=current_user,
        payload={"user_id": str(user_id), "role": member.role, "status": member.status},
    )
    session.commit()
    session.refresh(member)
    return _serialize_member(member, user)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_workspace_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    user_id: uuid.UUID,
    workspace_header: WorkspaceIdDep,
) -> Response:
    """Deactivate a workspace membership."""
    _ensure_workspace_path_matches_header(workspace_id, workspace_header)
    _workspace_or_404(session, workspace_id)
    member = _membership_or_404(session, workspace_id=workspace_id, user_id=user_id)
    _prevent_last_admin_removal(
        session,
        member,
        next_role=member.role,
        next_status=WORKSPACE_STATUS_INACTIVE,
    )
    member.status = WORKSPACE_STATUS_INACTIVE
    member.updated_at = datetime.now(timezone.utc)
    session.add(member)
    _audit(
        session,
        event_name="workspace.member_removed",
        workspace_id=member.workspace_id,
        current_user=current_user,
        payload={"user_id": str(user_id), "role": member.role, "status": member.status},
    )
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
