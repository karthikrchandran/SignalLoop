"""Tests for provider-credentials, provider-options, provider-selection routes."""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.encryption import encrypt
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
)

WORKSPACE_ID = "ws-providers"


def _headers(token_headers: dict[str, str]) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": WORKSPACE_ID}


# ---------------------------------------------------------------------------
# GET /provider-options
# ---------------------------------------------------------------------------


def test_list_provider_options_returns_catalog(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    resp = client.get(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-options",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    caps = {entry["capability"] for entry in body["data"]}
    # Every ProviderCapability enum value should be present.
    assert caps == {c.value for c in ProviderCapability}
    email_entry = next(e for e in body["data"] if e["capability"] == "email")
    providers = {p["provider"] for p in email_entry["providers"]}
    assert "sendgrid" in providers
    assert "smtp" in providers


def test_provider_options_requires_admin(client: TestClient) -> None:
    resp = client.get(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-options"
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PUT / GET /provider-selection
# ---------------------------------------------------------------------------


def test_upsert_and_list_provider_selection(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    # Initially nothing.
    list_resp = client.get(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-selection",
        headers=_headers(superuser_token_headers),
    )
    assert list_resp.status_code == 200
    initial_count = list_resp.json()["count"]

    put_resp = client.put(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-selection",
        headers=_headers(superuser_token_headers),
        json={"capability": "email", "provider": "smtp"},
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["provider"] == "smtp"
    assert put_resp.json()["capability"] == "email"
    assert put_resp.json()["is_active"] is True

    # Idempotent re-upsert -> same row (count unchanged).
    put_resp2 = client.put(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-selection",
        headers=_headers(superuser_token_headers),
        json={"capability": "email", "provider": "sendgrid"},
    )
    assert put_resp2.status_code == 200
    assert put_resp2.json()["provider"] == "sendgrid"
    assert put_resp2.json()["id"] == put_resp.json()["id"]

    list_resp2 = client.get(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-selection",
        headers=_headers(superuser_token_headers),
    )
    assert list_resp2.status_code == 200
    rows = list_resp2.json()["data"]
    email_rows = [r for r in rows if r["capability"] == "email"]
    assert len(email_rows) == 1
    assert email_rows[0]["provider"] == "sendgrid"


# ---------------------------------------------------------------------------
# POST /provider-credentials/{id}/test
# ---------------------------------------------------------------------------


def _seed_credential(
    db: Session,
    *,
    provider: NotificationProvider,
    channel: str,
    api_key: str = "x",
    config_json: dict | None = None,
) -> ProviderCredential:
    cred = ProviderCredential(
        workspace_id=WORKSPACE_ID,
        provider=provider,
        channel=channel,
        encrypted_api_key=encrypt(api_key),
        encrypted_api_secret=None,
        config_json=config_json or {},
        is_active=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


def test_test_credential_succeeds_for_sendgrid(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    cred = _seed_credential(
        db,
        provider=NotificationProvider.sendgrid,
        channel="email",
        config_json={"from_email": "from@example.com"},
    )

    resp = client.post(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-credentials/{cred.id}/test",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["provider"] == "sendgrid"
    assert body["channel"] == "email"
    assert "SendGridAdapter" in (body.get("detail") or "")


def test_test_credential_404_when_missing(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    bogus = uuid.uuid4()
    resp = client.post(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-credentials/{bogus}/test",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 404


def test_test_credential_returns_ok_false_for_unmapped_channel(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    cred = _seed_credential(
        db,
        provider=NotificationProvider.sendgrid,
        channel="scheduling",  # no capability mapping
    )

    resp = client.post(
        f"{settings.API_V1_STR}/workspaces/{WORKSPACE_ID}/provider-credentials/{cred.id}/test",
        headers=_headers(superuser_token_headers),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "scheduling" in (body.get("detail") or "")
