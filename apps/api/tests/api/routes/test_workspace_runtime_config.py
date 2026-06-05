"""Tests for workspace runtime-config endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings

WORKSPACE_ID = "ws-runtime-config"


def _headers(token_headers: dict[str, str], *, workspace_id: str = WORKSPACE_ID) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def test_runtime_config_requires_authentication(client: TestClient) -> None:
    resp = client.get(f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/runtime-config")
    assert resp.status_code == 401


def test_runtime_config_upsert_and_get(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    payload = {
        "deepgram_api_key": "dg-test-key",
        "groq_api_key": "groq-test-key",
        "team_notification_email": "ops@example.com",
    }

    post_resp = client.post(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/runtime-config",
        headers=_headers(superuser_token_headers),
        json=payload,
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["deepgram_configured"] is True
    assert post_resp.json()["groq_configured"] is True
    assert post_resp.json()["team_notification_email"] == "ops@example.com"
    assert post_resp.json()["sources"] == {
        "deepgram": "database",
        "groq": "database",
        "team_notifications": "database",
    }

    get_resp = client.get(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/runtime-config",
        headers=_headers(superuser_token_headers),
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["workspace_id"] == WORKSPACE_ID
    assert get_resp.json()["sources"]["deepgram"] == "database"
    assert get_resp.json()["sources"]["groq"] == "database"
    assert get_resp.json()["sources"]["team_notifications"] == "database"