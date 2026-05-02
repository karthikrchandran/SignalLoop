from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status

from app.api.deps import AdminUser


def semantic_error(code: str, message: str, semantic: str, details: dict | None = None):
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


def require_workspace_id(
    _admin_user: AdminUser,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> str:
    if not x_workspace_id:
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
    return x_workspace_id


WorkspaceIdDep = Annotated[str, Depends(require_workspace_id)]


def require_idempotency_key(idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> str:
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
