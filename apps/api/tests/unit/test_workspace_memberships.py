"""Tests for workspace membership authorization helpers."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import require_admin
from app.api.request_context import require_workspace_access, require_workspace_id
from app.domain.workspaces.models import Workspace, WorkspaceMembership
from app.domain.workspaces.service import (
    WORKSPACE_ADMIN_ROLES,
    ensure_workspace_membership,
    get_active_membership,
    user_has_workspace_access,
)
from app.models import User
from app.routers.chatbot.router import require_chatbot_agent


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(
        engine,
        tables=[User.__table__, Workspace.__table__, WorkspaceMembership.__table__],
    )
    return Session(engine)


def _user(*, role: str = "operator", is_superuser: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4().hex}@example.com",
        hashed_password="x",
        role=role,
        is_superuser=is_superuser,
    )


def test_user_can_have_multiple_workspace_memberships() -> None:
    with _session() as session:
        user = _user(role="viewer")
        session.add(user)
        session.flush()

        ensure_workspace_membership(session, workspace_id="ws-a", user_id=user.id, role="admin")
        ensure_workspace_membership(session, workspace_id="ws-b", user_id=user.id, role="agent")
        session.commit()

        assert get_active_membership(session, user_id=user.id, workspace_id="ws-a").role == "admin"
        assert get_active_membership(session, user_id=user.id, workspace_id="ws-b").role == "agent"
        assert user_has_workspace_access(session, user=user, workspace_id="ws-a", allowed_roles=WORKSPACE_ADMIN_ROLES)
        assert not user_has_workspace_access(session, user=user, workspace_id="ws-b", allowed_roles=WORKSPACE_ADMIN_ROLES)


def test_workspace_access_requires_membership_for_non_superusers() -> None:
    with _session() as session:
        user = _user()
        session.add(user)
        session.commit()

        with pytest.raises(HTTPException) as exc_info:
            require_workspace_access(user, session, "ws-a")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "WORKSPACE_ACCESS_DENIED"


def test_workspace_admin_role_can_authorize_admin_dependency() -> None:
    with _session() as session:
        user = _user(role="viewer")
        session.add(user)
        session.flush()
        ensure_workspace_membership(session, workspace_id="ws-a", user_id=user.id, role="admin")
        session.commit()

        assert require_admin(session, user, "ws-a") == user
        assert require_workspace_id(user, session, "ws-a") == "ws-a"


def test_global_admin_without_membership_cannot_select_workspace() -> None:
    with _session() as session:
        user = _user(role="admin")
        session.add(user)
        session.commit()

        assert require_admin(session, user, "ws-a") == user
        with pytest.raises(HTTPException) as exc_info:
            require_workspace_id(user, session, "ws-a")

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"]["code"] == "WORKSPACE_ACCESS_DENIED"


def test_superuser_bypasses_workspace_membership() -> None:
    with _session() as session:
        user = _user(is_superuser=True)
        session.add(user)
        session.commit()

        assert require_admin(session, user, "ws-any") == user
        assert require_workspace_id(user, session, "ws-any") == "ws-any"


def test_chatbot_agent_role_can_come_from_workspace_membership() -> None:
    with _session() as session:
        user = _user(role="viewer")
        session.add(user)
        session.flush()
        ensure_workspace_membership(session, workspace_id="ws-chat", user_id=user.id, role="agent")
        session.commit()

        assert require_workspace_access(user, session, "ws-chat") == "ws-chat"
        assert require_chatbot_agent(session, user, "ws-chat") == user
