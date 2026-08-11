"""Module: ``request context``."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import select

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.domain.support_access.service import (
    SupportAccessDenied,
    resolve_support_context,
)
from app.domain.tenants.models import Tenant
from app.domain.workspaces.service import (
    normalize_workspace_id,
    user_has_workspace_access,
)


def semantic_error(code: str, message: str, semantic: str, details: dict | None = None):
    """Semantic error."""
    correlation_id = str(uuid4())
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": code,
                "message": message,
                "semantic": semantic,
                "correlationId": correlation_id,
                "details": details or {},
            }
        },
    )


def _workspace_required_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": {
                "code": "WORKSPACE_REQUIRED",
                "message": "X-Workspace-Id header is required",
                "semantic": "AUTH_ERROR",
                "correlationId": str(uuid4()),
                "details": {},
            }
        },
    )


def _workspace_access_denied_error(workspace_id: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "WORKSPACE_ACCESS_DENIED",
                "message": "User is not a member of this workspace",
                "semantic": "AUTH_ERROR",
                "correlationId": str(uuid4()),
                "details": {"workspace_id": workspace_id},
            }
        },
    )


def _validated_workspace_header(x_workspace_id: str | None) -> str:
    if not x_workspace_id:
        _workspace_required_error()
    workspace_id = normalize_workspace_id(x_workspace_id)
    if not workspace_id:
        _workspace_required_error()
    if len(workspace_id) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "WORKSPACE_INVALID",
                    "message": "X-Workspace-Id must be 64 characters or fewer",
                    "semantic": "AUTH_ERROR",
                    "correlationId": str(uuid4()),
                    "details": {},
                }
            },
        )
    return workspace_id


def require_workspace_access(
    current_user: CurrentUser,
    session: SessionDep,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> str:
    """Validate workspace membership and return workspace id."""
    workspace_id = _validated_workspace_header(x_workspace_id)
    if user_has_workspace_access(session, user=current_user, workspace_id=workspace_id):
        return workspace_id
    _workspace_access_denied_error(workspace_id)
    raise AssertionError("unreachable")


def require_workspace_id(
    admin_user: AdminUser,
    session: SessionDep,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> str:
    """Validate admin workspace access and return workspace id."""
    workspace_id = _validated_workspace_header(x_workspace_id)
    if user_has_workspace_access(session, user=admin_user, workspace_id=workspace_id):
        return workspace_id
    _workspace_access_denied_error(workspace_id)
    raise AssertionError("unreachable")


WorkspaceIdDep = Annotated[str, Depends(require_workspace_id)]
WorkspaceAccessIdDep = Annotated[str, Depends(require_workspace_access)]


def require_workspace_access_with_support(required_capability: str):
    """Permit tenant access through a live, tenant-matched support grant."""

    def dependency(
        current_user: CurrentUser,
        session: SessionDep,
        x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
        x_support_grant_id: str | None = Header(
            default=None,
            alias="X-Support-Grant-Id",
        ),
    ) -> str:
        workspace_id = _validated_workspace_header(x_workspace_id)
        if x_support_grant_id:
            try:
                grant_id = UUID(x_support_grant_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            tenant = session.exec(select(Tenant).where(Tenant.key == workspace_id)).one_or_none()
            if tenant is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            try:
                resolve_support_context(
                    session,
                    grant_id=grant_id,
                    operator_user_id=current_user.id,
                    tenant_id=tenant.id,
                    required_capability=required_capability,
                )
                session.commit()
            except SupportAccessDenied:
                session.commit()
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
            return workspace_id

        if user_has_workspace_access(session, user=current_user, workspace_id=workspace_id):
            return workspace_id
        _workspace_access_denied_error(workspace_id)
        raise AssertionError("unreachable")

    return dependency


ContactsReadWorkspaceIdDep = Annotated[
    str,
    Depends(require_workspace_access_with_support("contacts.read")),
]


def require_idempotency_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
    """Validate and return idempotency key."""
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "IDEMPOTENCY_KEY_REQUIRED",
                    "message": "Idempotency-Key header is required",
                    "semantic": "POLICY_VIOLATION",
                    "correlationId": str(uuid4()),
                    "details": {},
                }
            },
        )
    return idempotency_key


IdempotencyKeyDep = Annotated[str, Depends(require_idempotency_key)]
