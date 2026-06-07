"""Tests for ``app.api.routes.utils`` HTTP endpoints (Group E coverage)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.core.encryption import encrypt
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkerHeartbeat,
    WorkspaceProviderSelection,
)

WORKSPACE_ID = "ws-setup-overview"


def _headers(token_headers: dict[str, str], *, workspace_id: str = WORKSPACE_ID) -> dict[str, str]:
    return {**token_headers, "X-Workspace-Id": workspace_id}


def _upsert_worker_heartbeat(db: Session, worker_key: str) -> None:
    row = db.get(WorkerHeartbeat, worker_key)
    now = datetime.now(timezone.utc)
    if row is None:
        db.add(
            WorkerHeartbeat(
                worker_key=worker_key,
                status="healthy",
                poll_interval_seconds=30,
                last_seen_at=now,
                updated_at=now,
            )
        )
        return

    row.status = "healthy"
    row.poll_interval_seconds = 30
    row.last_seen_at = now
    row.updated_at = now
    db.add(row)


def test_test_email_superuser_sends(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Superuser POST /utils/test-email/ returns 201 and invokes send_email."""
    with patch("app.api.routes.utils.send_email") as mock_send:
        resp = client.post(
            f"{settings.API_V1_STR}/utils/test-email/?email_to=qa@example.com",
            headers=superuser_token_headers,
        )
    assert resp.status_code == 201
    assert resp.json() == {"message": "Test email sent"}
    mock_send.assert_called_once()


def test_test_email_non_superuser_forbidden(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Non-superuser POST /utils/test-email/ is rejected with 403."""
    resp = client.post(
        f"{settings.API_V1_STR}/utils/test-email/?email_to=qa@example.com",
        headers=normal_user_token_headers,
    )
    assert resp.status_code == 403


def test_test_email_unauthenticated(client: TestClient) -> None:
    """Unauthenticated POST /utils/test-email/ returns 401."""
    resp = client.post(
        f"{settings.API_V1_STR}/utils/test-email/?email_to=qa@example.com",
    )
    assert resp.status_code == 401


def test_test_email_invalid_email_returns_422(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Malformed email rejected by EmailStr validator."""
    resp = client.post(
        f"{settings.API_V1_STR}/utils/test-email/?email_to=not-an-email",
        headers=superuser_token_headers,
    )
    assert resp.status_code == 422


def test_health_check_postgres_ok_no_redis(client: TestClient) -> None:
    """Health check returns api+postgres true; redis false when manager missing."""
    resp = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api"] is True
    assert body["postgres"] is True
    assert body["redis"] in (True, False)


def test_health_check_postgres_failure(client: TestClient) -> None:
    """When postgres ping raises, health-check returns postgres=False but still 200."""
    with patch("app.api.routes.utils._check_postgres_sync", return_value=False):
        resp = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    assert resp.status_code == 200
    assert resp.json()["postgres"] is False


def test_health_check_redis_ping_raises(client: TestClient) -> None:
    """Redis manager that raises is treated as redis=False."""

    class _BoomRedis:
        async def ping(self) -> bool:
            raise RuntimeError("boom")

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _BoomRedis()
    try:
        resp = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original
    assert resp.status_code == 200
    assert resp.json()["redis"] is False


def test_health_check_redis_ping_true(client: TestClient) -> None:
    """Redis manager returning True surfaces redis=True."""

    class _OkRedis:
        async def ping(self) -> bool:
            return True

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _OkRedis()
    try:
        resp = client.get(f"{settings.API_V1_STR}/utils/health-check/")
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original
    assert resp.status_code == 200
    assert resp.json()["redis"] is True


def test_liveness_probe(client: TestClient) -> None:
    """/utils/live always 200 ok."""
    resp = client.get(f"{settings.API_V1_STR}/utils/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_readiness_postgres_ok_redis_missing(client: TestClient) -> None:
    """Readiness returns 503 when redis manager is absent."""
    original = getattr(client.app.state, "redis_manager", None)
    if original is not None:
        try:
            del client.app.state.redis_manager
        except AttributeError:
            pass
    try:
        resp = client.get(f"{settings.API_V1_STR}/utils/ready")
    finally:
        if original is not None:
            client.app.state.redis_manager = original
    # postgres healthy, redis missing -> not ready
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["postgres"] is True
    assert body["checks"]["redis"] is False


def test_readiness_all_healthy(client: TestClient) -> None:
    """Readiness returns 200 when every dep responds."""

    class _OkRedis:
        async def ping(self) -> bool:
            return True

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _OkRedis()
    try:
        resp = client.get(f"{settings.API_V1_STR}/utils/ready")
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["postgres"] is True
    assert body["checks"]["redis"] is True


def test_readiness_redis_raises(client: TestClient) -> None:
    """Readiness returns 503 when redis ping raises."""

    class _BoomRedis:
        async def ping(self) -> bool:
            raise RuntimeError("redis down")

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _BoomRedis()
    try:
        resp = client.get(f"{settings.API_V1_STR}/utils/ready")
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original
    assert resp.status_code == 503
    assert resp.json()["checks"]["redis"] is False


def test_readiness_postgres_failure(client: TestClient) -> None:
    """Readiness returns 503 when postgres connect raises."""
    from app.api.routes import utils as utils_mod

    class _BoomEngine:
        def connect(self):  # noqa: D401, ANN001
            raise RuntimeError("pg down")

    with patch.object(utils_mod, "engine", _BoomEngine()):
        resp = client.get(f"{settings.API_V1_STR}/utils/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"]["postgres"] is False


def test_setup_overview_requires_authentication(client: TestClient) -> None:
    """Setup overview is admin-only."""
    resp = client.get(f"{settings.API_V1_STR}/utils/setup-overview/")
    assert resp.status_code == 401


def test_setup_overview_returns_workspace_setup_summary(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """Setup overview surfaces provider status, callbacks, and worker readiness."""

    workspace_id = f"ws-setup-overview-{uuid.uuid4().hex[:8]}"
    db.add(
        ProviderCredential(
            workspace_id=workspace_id,
            provider=NotificationProvider.sendgrid,
            channel="email",
            encrypted_api_key=encrypt("SG.test"),
            encrypted_api_secret=None,
            config_json={"from_email": "ops@example.com"},
            is_active=True,
        )
    )
    _upsert_worker_heartbeat(db, "sequence_worker")
    _upsert_worker_heartbeat(db, "call_worker")
    _upsert_worker_heartbeat(db, "postcall_worker")
    db.commit()

    class _OkRedis:
        async def ping(self) -> bool:
            return True

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _OkRedis()
    try:
        with patch.object(settings, "SERVER_HOST", "public.example.com"), patch.object(
            settings, "TWILIO_ACCOUNT_SID", "acct"
        ), patch.object(settings, "TWILIO_AUTH_TOKEN", "token"), patch.object(
            settings, "TWILIO_PHONE_NUMBER", "+15551234567"
        ), patch.object(settings, "DEEPGRAM_API_KEY", "deepgram-key"), patch.object(
            settings, "GROQ_API_KEY", "groq-key"
        ), patch.object(settings, "TEAM_NOTIFICATION_EMAIL", "ops@example.com"):
            resp = client.get(
                f"{settings.API_V1_STR}/utils/setup-overview/",
                headers=_headers(superuser_token_headers, workspace_id=workspace_id),
            )
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original

    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace_id"] == workspace_id
    assert body["health"] == {"api": True, "postgres": True, "redis": True}
    assert body["callbacks"]["public_host"] is True
    assert body["callbacks"]["sendgrid_webhook_url"].endswith("/api/v1/webhooks/sendgrid")
    integrations = {item["key"]: item for item in body["integrations"]}
    assert integrations["email"]["provider"] == "sendgrid"
    assert integrations["email"]["source"] == "database"
    assert integrations["email"]["configured"] is True
    assert integrations["sms"]["provider"] == "twilio"
    assert integrations["sms"]["source"] == "environment"
    assert integrations["voice"]["provider"] == "twilio"
    assert integrations["voice"]["source"] == "environment"
    assert integrations["stt"]["provider"] == "deepgram"
    assert integrations["stt"]["configured"] is True
    assert integrations["tts"]["provider"] == "deepgram"
    assert integrations["tts"]["configured"] is True
    assert integrations["llm"]["provider"] == "groq"
    assert integrations["llm"]["configured"] is True
    assert integrations["team_notifications"]["configured"] is True
    worker_readiness = {item["key"]: item for item in body["worker_readiness"]}
    assert worker_readiness["sequence_worker"]["ready"] is True
    assert worker_readiness["call_worker"]["ready"] is True
    assert worker_readiness["postcall_worker"]["ready"] is True


def test_setup_overview_reports_missing_runtime_dependencies(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    """Local callback hosts and missing runtime keys surface as readiness blockers."""

    original = getattr(client.app.state, "redis_manager", None)
    if original is not None:
        try:
            del client.app.state.redis_manager
        except AttributeError:
            pass
    try:
        with patch.object(settings, "SERVER_HOST", "localhost:8001"), patch.object(
            settings, "SENDGRID_API_KEY", ""
        ), patch.object(settings, "TWILIO_ACCOUNT_SID", ""), patch.object(
            settings, "TWILIO_AUTH_TOKEN", ""
        ), patch.object(settings, "DEEPGRAM_API_KEY", ""), patch.object(
            settings, "GROQ_API_KEY", ""
        ), patch.object(settings, "TEAM_NOTIFICATION_EMAIL", ""):
            resp = client.get(
                f"{settings.API_V1_STR}/utils/setup-overview/",
                headers=_headers(superuser_token_headers, workspace_id=f"ws-missing-{uuid.uuid4().hex[:8]}"),
            )
    finally:
        if original is not None:
            client.app.state.redis_manager = original

    assert resp.status_code == 200
    body = resp.json()
    assert body["callbacks"]["public_host"] is False
    worker_readiness = {item["key"]: item for item in body["worker_readiness"]}
    assert worker_readiness["sequence_worker"]["ready"] is False
    assert "redis" in worker_readiness["sequence_worker"]["missing"]
    assert "email_provider" in worker_readiness["sequence_worker"]["missing"]
    assert "voice_provider" in worker_readiness["call_worker"]["missing"]
    assert "stt_provider" in worker_readiness["call_worker"]["missing"]
    assert "tts_provider" in worker_readiness["call_worker"]["missing"]
    assert "llm_provider" in worker_readiness["call_worker"]["missing"]
    assert "public_callbacks" in worker_readiness["call_worker"]["missing"]


def test_setup_overview_uses_active_local_provider_selections(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """Setup overview reports local/open-source selections as active providers."""

    workspace_id = f"ws-local-providers-{uuid.uuid4().hex[:8]}"
    db.add(
        ProviderCredential(
            workspace_id=workspace_id,
            provider=NotificationProvider.smtp,
            channel="email",
            encrypted_api_key=encrypt("smtp-local"),
            encrypted_api_secret=None,
            config_json={
                "host": "localhost",
                "port": 1025,
                "from_email": "demo@example.com",
            },
            is_active=True,
        )
    )
    db.add(
        WorkspaceProviderSelection(
            workspace_id=workspace_id,
            capability=ProviderCapability.email,
            provider=NotificationProvider.smtp,
            is_active=True,
        )
    )
    db.add(
        WorkspaceProviderSelection(
            workspace_id=workspace_id,
            capability=ProviderCapability.stt,
            provider=NotificationProvider.faster_whisper_local,
            is_active=True,
        )
    )
    db.add(
        WorkspaceProviderSelection(
            workspace_id=workspace_id,
            capability=ProviderCapability.llm,
            provider=NotificationProvider.ollama_local,
            is_active=True,
        )
    )
    _upsert_worker_heartbeat(db, "sequence_worker")
    _upsert_worker_heartbeat(db, "call_worker")
    db.commit()

    class _OkRedis:
        async def ping(self) -> bool:
            return True

    original = getattr(client.app.state, "redis_manager", None)
    client.app.state.redis_manager = _OkRedis()
    try:
        with patch.object(settings, "SERVER_HOST", "public.example.com"), patch.object(
            settings, "TWILIO_ACCOUNT_SID", ""
        ), patch.object(settings, "TWILIO_AUTH_TOKEN", ""), patch.object(
            settings, "TWILIO_PHONE_NUMBER", ""
        ), patch.object(settings, "DEEPGRAM_API_KEY", ""), patch.object(
            settings, "GROQ_API_KEY", ""
        ), patch.object(settings, "TEAM_NOTIFICATION_EMAIL", ""):
            resp = client.get(
                f"{settings.API_V1_STR}/utils/setup-overview/",
                headers=_headers(superuser_token_headers, workspace_id=workspace_id),
            )
    finally:
        if original is None:
            try:
                del client.app.state.redis_manager
            except AttributeError:
                pass
        else:
            client.app.state.redis_manager = original

    assert resp.status_code == 200
    body = resp.json()
    integrations = {item["key"]: item for item in body["integrations"]}
    assert integrations["email"]["provider"] == "smtp"
    assert integrations["email"]["configured"] is True
    assert integrations["email"]["local"] is True
    assert integrations["email"]["config"]["host"] == "localhost"
    assert integrations["stt"]["provider"] == "faster_whisper_local"
    assert integrations["stt"]["configured"] is True
    assert integrations["stt"]["local"] is True
    assert integrations["llm"]["provider"] == "ollama_local"
    assert integrations["llm"]["configured"] is True
    assert integrations["llm"]["local"] is True

    worker_readiness = {item["key"]: item for item in body["worker_readiness"]}
    assert "email_provider" not in worker_readiness["sequence_worker"]["missing"]
    assert "stt_provider" not in worker_readiness["call_worker"]["missing"]
    assert "llm_provider" not in worker_readiness["call_worker"]["missing"]
    assert "voice_provider" in worker_readiness["call_worker"]["missing"]
    assert "tts_provider" in worker_readiness["call_worker"]["missing"]
