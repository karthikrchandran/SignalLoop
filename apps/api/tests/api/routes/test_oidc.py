from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import oidc
from app.core.config import settings
from app.domain.identity.models import OidcIdentity
from app.domain.identity.oidc import OidcSubject
from app.domain.tenants.models import Tenant
from app.domain.tenants.service import create_invitation


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def setex(self, key: str, _ttl: int, value: str) -> None:
        self.values[key] = value

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)


@pytest.fixture
def oidc_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUTH_MODE", "oidc")
    monkeypatch.setattr(settings, "OIDC_ISSUER", "https://id.example.test")
    monkeypatch.setattr(settings, "OIDC_CLIENT_ID", "client-123")
    monkeypatch.setattr(settings, "OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setattr(settings, "OIDC_REDIRECT_URI", "https://app.example.test/auth/callback")
    monkeypatch.setattr(settings, "OIDC_AUDIENCE", "client-123")


def test_oidc_start_binds_a_named_invitation_to_the_server_transaction(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    oidc_settings: None,
) -> None:
    tenant = Tenant(key=f"ara-{uuid4().hex}", display_name="ARA Global")
    db.add(tenant)
    db.commit()
    invitation_token, invitation = create_invitation(
        db,
        tenant_id=tenant.id,
        email="owner@example.com",
        ttl=timedelta(hours=1),
    )
    db.commit()
    redis = FakeRedis()
    redis_manager = client.app.state.redis_manager
    original_redis = redis_manager.client
    redis_manager.client = redis
    monkeypatch.setattr(
        oidc,
        "discover_oidc_configuration",
        lambda _issuer: {"authorization_endpoint": "https://id.example.test/authorize"},
    )

    _ = oidc_settings
    try:
        response = client.get(
            f"{settings.API_V1_STR}/auth/oidc/start",
            params={"invitation_token": invitation_token, "return_to": "/home"},
            follow_redirects=False,
        )
    finally:
        redis_manager.client = original_redis

    assert response.status_code == 307
    assert response.headers["location"].startswith("https://id.example.test/authorize?")
    assert "oidc_tx=" in response.headers["set-cookie"]
    stored = json.loads(next(iter(redis.values.values())))
    assert stored["tenant_id"] == str(tenant.id)
    assert stored["invitation_id"] == str(invitation.id)
    assert stored["return_path"] == "/home"


def test_oidc_callback_activates_the_bound_invitation_once(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    oidc_settings: None,
) -> None:
    tenant = Tenant(key=f"ara-{uuid4().hex}", display_name="ARA Global")
    db.add(tenant)
    db.commit()
    invitation_token, invitation = create_invitation(
        db,
        tenant_id=tenant.id,
        email="owner@example.com",
        ttl=timedelta(hours=1),
    )
    db.commit()
    redis = FakeRedis()
    redis_manager = client.app.state.redis_manager
    original_redis = redis_manager.client
    redis_manager.client = redis
    _ = oidc_settings
    monkeypatch.setattr(
        oidc,
        "discover_oidc_configuration",
        lambda _issuer: {"authorization_endpoint": "https://id.example.test/authorize"},
    )

    try:
        start = client.get(
            f"{settings.API_V1_STR}/auth/oidc/start",
            params={"invitation_token": invitation_token, "return_to": "/home"},
            follow_redirects=False,
        )
        state = start.next_request.url.params["state"]  # type: ignore[union-attr]

        async def fake_exchange(*_args: object, **_kwargs: object) -> OidcSubject:
            return OidcSubject(
                issuer="https://id.example.test",
                subject="subject-1",
                email="owner@example.com",
                email_verified=True,
            )

        monkeypatch.setattr(oidc, "exchange_and_validate", fake_exchange)
        callback = client.get(
            f"{settings.API_V1_STR}/auth/oidc/callback",
            params={"code": "opaque-code", "state": state},
            follow_redirects=False,
        )
        authenticated = client.post(f"{settings.API_V1_STR}/login/test-token")
        replay = client.get(
            f"{settings.API_V1_STR}/auth/oidc/callback",
            params={"code": "opaque-code", "state": state},
            follow_redirects=False,
        )
    finally:
        redis_manager.client = original_redis

    assert callback.status_code == 307
    assert callback.headers["location"].endswith("/home")
    assert "access_token=" in callback.headers["set-cookie"]
    assert authenticated.status_code == 200
    assert authenticated.json()["email"] == "owner@example.com"
    assert replay.status_code == 400
    db.refresh(invitation)
    assert invitation.status == "ACCEPTED"
    assert db.exec(select(OidcIdentity)).one().subject == "subject-1"
