from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.core.config import settings
from app.core.db import engine


@pytest.fixture(scope="module", autouse=True)
def ensure_governance_tables() -> None:
    SQLModel.metadata.create_all(engine)


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


def test_daily_caps_policy_blocks_excess_actions(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-4-caps")
    create_policy_response = client.post(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id, idempotency=True),
        json={
            "scope": "workspace",
            "policy_type": "daily_caps",
            "payload_json": {"campaignDailyCap": 1, "systemDailyCap": 5},
        },
    )
    assert create_policy_response.status_code == 200

    evaluate_response = client.post(
        f"{settings.API_V1_STR}/policies/evaluate",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
        json={
            "contact": {"timezone": "UTC", "suppressed": False},
            "campaign_daily_count": 1,
            "system_daily_count": 0,
        },
    )
    assert evaluate_response.status_code == 200
    payload = evaluate_response.json()
    assert payload["allowed"] is False
    assert payload["reason_code"] == "CAMPAIGN_CAP_EXCEEDED"
    assert payload["semantic_error"] == "POLICY_VIOLATION"


def test_quiet_hours_policy_defers_next_eligible_time(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-4-quiet")
    create_policy_response = client.post(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id, idempotency=True),
        json={
            "scope": "workspace",
            "policy_type": "quiet_hours",
            "payload_json": {"start": "21:00", "end": "08:00", "timezone": "UTC"},
        },
    )
    assert create_policy_response.status_code == 200

    evaluate_response = client.post(
        f"{settings.API_V1_STR}/policies/evaluate",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
        json={
            "contact": {"timezone": "UTC", "suppressed": False},
            "campaign_daily_count": 0,
            "system_daily_count": 0,
            "requested_at": datetime(2026, 4, 1, 22, 30, tzinfo=UTC).isoformat(),
        },
    )
    assert evaluate_response.status_code == 200
    payload = evaluate_response.json()
    assert payload["allowed"] is False
    assert payload["reason_code"] == "QUIET_HOURS_BLOCK"
    assert payload["next_eligible_at"] is not None


def test_suppression_policy_skips_suppressed_contact(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    workspace_id = _workspace("story-1-4-suppression")
    create_policy_response = client.post(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id, idempotency=True),
        json={
            "scope": "workspace",
            "policy_type": "suppression",
            "payload_json": {},
        },
    )
    assert create_policy_response.status_code == 200

    evaluate_response = client.post(
        f"{settings.API_V1_STR}/policies/evaluate",
        headers=_headers(superuser_token_headers, workspace_id=workspace_id),
        json={
            "contact": {"timezone": "UTC", "suppressed": True},
            "campaign_daily_count": 0,
            "system_daily_count": 0,
        },
    )
    assert evaluate_response.status_code == 200
    payload = evaluate_response.json()
    assert payload["allowed"] is False
    assert payload["reason_code"] == "SUPPRESSED_CONTACT"


def test_workspace_isolation_hides_policies_and_rejects_cross_scope_campaign_mutation(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    source_workspace = _workspace("story-1-4-source")
    other_workspace = _workspace("story-1-4-other")

    create_policy_response = client.post(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=source_workspace, idempotency=True),
        json={
            "scope": "workspace",
            "policy_type": "suppression",
            "payload_json": {},
        },
    )
    assert create_policy_response.status_code == 200

    read_other_workspace_response = client.get(
        f"{settings.API_V1_STR}/policies/",
        headers=_headers(superuser_token_headers, workspace_id=other_workspace),
    )
    assert read_other_workspace_response.status_code == 200
    assert read_other_workspace_response.json()["count"] == 0

    create_campaign_response = client.post(
        f"{settings.API_V1_STR}/campaigns/",
        headers=_headers(superuser_token_headers, workspace_id=source_workspace, idempotency=True),
        json={"name": "Campaign for pause check"},
    )
    assert create_campaign_response.status_code == 200
    campaign_id = create_campaign_response.json()["id"]

    pause_other_workspace_response = client.post(
        f"{settings.API_V1_STR}/campaigns/{campaign_id}/pause",
        headers=_headers(superuser_token_headers, workspace_id=other_workspace, idempotency=True),
        json={"paused_reason": "Attempt cross workspace pause"},
    )
    assert pause_other_workspace_response.status_code == 404


def test_operator_denied_admin_controls(
    client: TestClient,
    superuser_token_headers: dict[str, str],
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
