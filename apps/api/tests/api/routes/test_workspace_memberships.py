"""HTTP tests for workspace membership enforcement."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.domain.workspaces.service import ensure_workspace_membership
from app.models import User, UserCreate
from tests.utils.user import user_authentication_headers


def _create_user(
    *,
    client: TestClient,
    db: Session,
    role: str = "viewer",
) -> tuple[dict[str, str], User]:
    password = f"Pass-{uuid.uuid4().hex[:12]}"
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"workspace-{uuid.uuid4().hex}@example.com",
            password=password,
            role=role,
        ),
    )
    return user_authentication_headers(client=client, email=user.email, password=password), user


def _create_user_with_workspace_role(
    *,
    client: TestClient,
    db: Session,
    workspace_id: str,
    role: str,
) -> tuple[dict[str, str], User]:
    headers, user = _create_user(client=client, db=db)
    ensure_workspace_membership(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        role=role,
    )
    db.commit()
    return headers, user


def test_workspace_admin_membership_allows_workspace_route(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-membership-{uuid.uuid4().hex[:8]}"
    headers, _ = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )

    response = client.get(
        f"{settings.API_V1_STR}/campaigns/",
        headers={**headers, "X-Workspace-Id": workspace_id},
    )

    assert response.status_code == 200


def test_workspace_admin_membership_rejects_unassigned_workspace(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-membership-{uuid.uuid4().hex[:8]}"
    other_workspace_id = f"ws-membership-other-{uuid.uuid4().hex[:8]}"
    headers, _ = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )

    response = client.get(
        f"{settings.API_V1_STR}/campaigns/",
        headers={**headers, "X-Workspace-Id": other_workspace_id},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["semantic"] == "AUTH_ERROR"


def test_superuser_can_create_workspace_and_list_owner_membership(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = f"ws-admin-api-{uuid.uuid4().hex[:8]}"

    create_response = client.post(
        f"{settings.API_V1_STR}/workspaces/",
        headers=superuser_token_headers,
        json={"id": workspace_id, "display_name": "Admin API Workspace"},
    )
    assert create_response.status_code == 201
    assert create_response.json()["id"] == workspace_id

    list_response = client.get(
        f"{settings.API_V1_STR}/workspaces/",
        headers=superuser_token_headers,
    )
    assert list_response.status_code == 200
    assert workspace_id in {row["id"] for row in list_response.json()["data"]}

    members_response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members",
        headers={**superuser_token_headers, "X-Workspace-Id": workspace_id},
    )
    assert members_response.status_code == 200
    members = members_response.json()["data"]
    assert members
    assert members[0]["role"] == "owner"


def test_workspace_admin_can_add_and_list_member(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-admin-api-{uuid.uuid4().hex[:8]}"
    admin_headers, _ = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )
    _, target_user = _create_user(client=client, db=db)

    put_response = client.put(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members/{target_user.id}",
        headers={**admin_headers, "X-Workspace-Id": workspace_id},
        json={"role": "agent"},
    )
    assert put_response.status_code == 200
    assert put_response.json()["role"] == "agent"
    assert put_response.json()["status"] == "active"

    list_response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members",
        headers={**admin_headers, "X-Workspace-Id": workspace_id},
    )
    assert list_response.status_code == 200
    assert str(target_user.id) in {row["user_id"] for row in list_response.json()["data"]}


def test_workspace_admin_cannot_demote_last_active_admin(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-admin-api-{uuid.uuid4().hex[:8]}"
    admin_headers, admin_user = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )

    response = client.patch(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members/{admin_user.id}",
        headers={**admin_headers, "X-Workspace-Id": workspace_id},
        json={"role": "operator"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "LAST_WORKSPACE_ADMIN"


def test_workspace_admin_can_deactivate_member_when_another_admin_exists(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-admin-api-{uuid.uuid4().hex[:8]}"
    admin_headers, _ = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )
    _, second_admin = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="admin",
    )

    delete_response = client.delete(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members/{second_admin.id}",
        headers={**admin_headers, "X-Workspace-Id": workspace_id},
    )
    assert delete_response.status_code == 204

    members_response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members",
        params={"status": "all"},
        headers={**admin_headers, "X-Workspace-Id": workspace_id},
    )
    assert members_response.status_code == 200
    members_by_user = {row["user_id"]: row for row in members_response.json()["data"]}
    assert members_by_user[str(second_admin.id)]["status"] == "inactive"


def test_non_admin_member_cannot_manage_members(
    client: TestClient,
    db: Session,
) -> None:
    workspace_id = f"ws-admin-api-{uuid.uuid4().hex[:8]}"
    operator_headers, _ = _create_user_with_workspace_role(
        client=client,
        db=db,
        workspace_id=workspace_id,
        role="operator",
    )

    response = client.get(
        f"{settings.API_V1_STR}/workspaces/{workspace_id}/members",
        headers={**operator_headers, "X-Workspace-Id": workspace_id},
    )

    assert response.status_code == 403
