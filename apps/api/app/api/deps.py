"""Module: ``deps``."""

from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.domain.identity.sessions import SessionRevoked, resolve_session
from app.domain.workspaces.service import (
    WORKSPACE_ADMIN_ROLES,
    user_has_workspace_access,
)
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def get_db() -> Generator[Session, None, None]:
    """Return db."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str | None, Depends(reusable_oauth2)]


def get_current_user(request: Request, session: SessionDep, token: TokenDep) -> User:
    """Return current user."""
    if token is None:
        session_token = request.cookies.get("access_token")
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user_id = resolve_session(session, session_token)
        except SessionRevoked as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            ) from exc
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
            )
        return user
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]

_AUTH_ERROR = {
    "error": {
        "code": "AUTH_ERROR",
        "message": "Admin privileges are required",
        "semantic": "AUTH_ERROR",
        "details": {},
    }
}


def require_admin(
    session: SessionDep,
    current_user: CurrentUser,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> User:
    """Validate and return admin."""
    if current_user.is_superuser or getattr(current_user, "role", None) in {
        "admin",
        "super_admin",
    }:
        return current_user
    if x_workspace_id and user_has_workspace_access(
        session,
        user=current_user,
        workspace_id=x_workspace_id,
        allowed_roles=WORKSPACE_ADMIN_ROLES,
    ):
        return current_user
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_AUTH_ERROR,
    )


AdminUser = Annotated[User, Depends(require_admin)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    """Return current active superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
