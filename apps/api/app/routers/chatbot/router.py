"""ChatBot Hub foundation routes."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import WorkspaceAccessIdDep
from app.domain.chatbot.schemas import (
    ChatbotHealthPublic,
    ChatbotNavigationItem,
    ChatbotNavigationPublic,
)
from app.domain.workspaces.service import (
    WORKSPACE_AGENT_ROLES,
    WORKSPACE_OPERATOR_ROLES,
    user_has_workspace_access,
)
from app.models import User

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

CHATBOT_ADMIN_ROLES = {"admin", "super_admin"}
CHATBOT_AGENT_ROLES = {"admin", "super_admin", "agent", "support_agent", "operator"}
CHATBOT_OPERATOR_ROLES = {"operator", "super_admin"}


def _auth_error(message: str = "ChatBot Hub privileges are required") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": "AUTH_ERROR",
                "message": message,
                "semantic": "AUTH_ERROR",
                "correlationId": str(uuid4()),
                "details": {},
            }
        },
    )


WorkspaceId = WorkspaceAccessIdDep


def _has_chatbot_role(
    *,
    session: SessionDep,
    current_user: User,
    workspace_id: str | None,
    global_roles: set[str],
    workspace_roles: set[str],
) -> bool:
    role = getattr(current_user, "role", None)
    if current_user.is_superuser or role in global_roles:
        return True
    return bool(
        workspace_id
        and user_has_workspace_access(
            session,
            user=current_user,
            workspace_id=workspace_id,
            allowed_roles=workspace_roles,
        )
    )


def require_chatbot_admin(
    session: SessionDep,
    current_user: CurrentUser,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> User:
    """Require workspace admin permissions for ChatBot Hub setup surfaces."""
    return require_admin(session, current_user, x_workspace_id)


def require_chatbot_agent(
    session: SessionDep,
    current_user: CurrentUser,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> User:
    """Allow admins and support agents to access shared ChatBot Hub read surfaces."""
    if _has_chatbot_role(
        session=session,
        current_user=current_user,
        workspace_id=x_workspace_id,
        global_roles=CHATBOT_AGENT_ROLES,
        workspace_roles=WORKSPACE_AGENT_ROLES,
    ):
        return current_user
    raise _auth_error()


def require_chatbot_operator(
    session: SessionDep,
    current_user: CurrentUser,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> User:
    """Require operator privileges for platform recovery surfaces."""
    if _has_chatbot_role(
        session=session,
        current_user=current_user,
        workspace_id=x_workspace_id,
        global_roles=CHATBOT_OPERATOR_ROLES,
        workspace_roles=WORKSPACE_OPERATOR_ROLES,
    ):
        return current_user
    raise _auth_error("Operator privileges are required")


def _navigation_for_user(current_user: User) -> list[ChatbotNavigationItem]:
    role = getattr(current_user, "role", None)
    is_admin = current_user.is_superuser or role in CHATBOT_ADMIN_ROLES
    items = [
        ChatbotNavigationItem(key="inbox", title="Inbox", path="/chatbot/inbox"),
        ChatbotNavigationItem(key="analytics", title="Analytics", path="/chatbot/analytics"),
    ]
    if is_admin:
        return [
            ChatbotNavigationItem(key="channels", title="Channels", path="/chatbot/channels", admin_only=True),
            ChatbotNavigationItem(
                key="knowledge_base",
                title="Knowledge Base",
                path="/chatbot/knowledge-base",
                admin_only=True,
            ),
            *items,
            ChatbotNavigationItem(key="settings", title="Settings", path="/chatbot/settings", admin_only=True),
        ]
    return items


@router.get("/health", response_model=ChatbotHealthPublic)
def read_chatbot_health(
    workspace_id: WorkspaceId,
    _current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotHealthPublic:
    """Return a small authenticated health response for the ChatBot Hub surface."""
    return ChatbotHealthPublic(status="ok", workspace_id=workspace_id)


@router.get("/routes", response_model=ChatbotNavigationPublic)
def list_chatbot_routes(
    _workspace_id: WorkspaceId,
    current_user: Annotated[User, Depends(require_chatbot_agent)],
) -> ChatbotNavigationPublic:
    """Return role-filtered route metadata for ChatBot Hub clients."""
    data = _navigation_for_user(current_user)
    return ChatbotNavigationPublic(data=data, count=len(data))


@router.get("/admin/health", response_model=ChatbotHealthPublic)
def read_chatbot_admin_health(
    workspace_id: WorkspaceId,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotHealthPublic:
    """Smoke-check admin-only ChatBot Hub access."""
    return ChatbotHealthPublic(status="ok", workspace_id=workspace_id)


@router.get("/operator/health", response_model=ChatbotHealthPublic)
def read_chatbot_operator_health(
    workspace_id: WorkspaceId,
    _current_user: Annotated[User, Depends(require_chatbot_operator)],
) -> ChatbotHealthPublic:
    """Smoke-check operator-only ChatBot Hub recovery access."""
    return ChatbotHealthPublic(status="ok", workspace_id=workspace_id)


from app.routers.chatbot import (  # noqa: E402
    analytics,
    channels,
    config,
    dead_letters,
    inbox,
    knowledge_sources,
    opt_outs,
    webhooks,
)

router.include_router(analytics.router)
router.include_router(channels.router)
router.include_router(config.router)
router.include_router(dead_letters.router)
router.include_router(inbox.router)
router.include_router(knowledge_sources.router)
router.include_router(opt_outs.router)
router.include_router(webhooks.router)
