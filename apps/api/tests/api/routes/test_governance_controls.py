from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.domain_models import Campaign


def _headers(
    token_headers: dict[str, str],
    *,
    workspace_id: str,
    idempotency: bool = False,
) -> dict[str, str]:
    headers = {**token_headers, "X-Workspace-Id": workspace_id}
    if idempotency:
        headers["Idempotency-Key"] = "test-idempotency-key"
    return headers


def _workspace(label: str) -> str:
    return f"ws-{label}-{uuid4().hex[:8]}"


def test_policy_routes_removed(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-2-policies")

    list_response = client.get(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
    )
    assert list_response.status_code == 404

    evaluate_response = client.post(
        f"{settings.API_V1_STR}/policies/evaluate",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
        json={},
    )
    assert evaluate_response.status_code == 404


def test_admin_can_read_workspace_scoped_routes(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-2-admin")

    response = client.get(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
    )
    assert response.status_code == 200


def test_operator_denied_former_public_and_operator_routes(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-2-operator")
    workspace_headers = _headers(normal_user_token_headers, workspace_id=workspace_id)

    protected_gets = [
        f"{settings.API_V1_STR}/campaigns/",
        f"{settings.API_V1_STR}/calls/",
        f"{settings.API_V1_STR}/scripts/",
        f"{settings.API_V1_STR}/sequences/",
        f"{settings.API_V1_STR}/dashboard/daily-cap-status",
        f"{settings.API_V1_STR}/signals/contacts/{uuid4()}",
    ]
    for path in protected_gets:
        response = client.get(path, headers=workspace_headers)
        assert response.status_code == 403

    trigger_response = client.get(
        f"{settings.API_V1_STR}/triggers/",
        headers=normal_user_token_headers,
    )
    assert trigger_response.status_code == 403

    create_campaign_response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(normal_user_token_headers, workspace_id=workspace_id, idempotency=True),
        json={"name": "Operator should not create campaigns"},
    )
    assert create_campaign_response.status_code == 403


def test_unauthenticated_former_public_routes_rejected(client: TestClient) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/calls/",
        headers={"X-Workspace-Id": _workspace("story-1-2-anonymous")},
    )
    assert response.status_code in {401, 403}


def test_workspace_isolation_rejects_cross_scope_campaign_mutation(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    source_workspace = _workspace("story-1-4-source")
    other_workspace = _workspace("story-1-4-other")

    campaign = Campaign(
        name="Campaign for pause check",
        workspace_id=source_workspace,
        created_by=uuid4(),
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    pause_other_workspace_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign.id}/pause",
        headers=_headers(superuser_token_headers, workspace_id=other_workspace, idempotency=True),
        json={"paused_reason": "Attempt cross workspace pause"},
    )
    assert pause_other_workspace_response.status_code == 404


def test_operator_denied_admin_controls(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-4-approval")

    denied_pause_response = client.post(
        f"{settings.API_V1_STR}/controls/pause",
        headers=_headers(normal_user_token_headers, workspace_id=workspace_id, idempotency=True),
        json={"paused_reason": "Not authorized"},
    )
    assert denied_pause_response.status_code == 403
    denied_error = denied_pause_response.json()["detail"]["error"]
    assert denied_error["code"] == "AUTH_ERROR"
    assert denied_error["semantic"] == "AUTH_ERROR"
