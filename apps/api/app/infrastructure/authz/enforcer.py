from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.deps import CurrentUser

_AUTH_ERROR = {"error": {"code": "AUTH_ERROR", "semantic": "AUTH_ERROR"}}


def require_role(role: str = "admin"):
    """Simple role check — MVP has only admin users."""

    def dependency(current_user: CurrentUser) -> CurrentUser:
        if current_user.is_superuser:
            return current_user
        if getattr(current_user, "role", None) == role or role == "operator":
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_AUTH_ERROR,
        )

    return dependency


def require_permission(resource: str, action: str):
    """No-op permission check for MVP — all admins have all permissions."""
    def dependency(current_user: CurrentUser) -> CurrentUser:
        if not current_user.is_superuser:
            if not getattr(current_user, "role", None):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=_AUTH_ERROR,
                )
        return current_user
    return dependency
