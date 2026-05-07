"""Tests for ``app.api.routes.utils`` HTTP endpoints (Group E coverage)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings


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
