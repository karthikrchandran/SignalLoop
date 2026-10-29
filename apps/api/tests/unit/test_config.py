from typing import Literal
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine

from app.core.config import Settings


def _make_settings(
    *,
    frontend_host: str,
    backend_cors_origins: list[str] | None = None,
    environment: Literal["local", "staging", "production"] = "local",
) -> Settings:
    return Settings(
        _env_file=None,
        PROJECT_NAME="Test",
        SECRET_KEY="test-secret",
        FRONTEND_HOST=frontend_host,
        ENVIRONMENT=environment,
        BACKEND_CORS_ORIGINS=backend_cors_origins or [],
        POSTGRES_SERVER="localhost",
        POSTGRES_USER="postgres",
        FIRST_SUPERUSER="admin@example.com",
        FIRST_SUPERUSER_PASSWORD="test-password",
    )


def test_local_cors_origins_include_loopback_alias_for_frontend_host() -> None:
    settings = _make_settings(frontend_host="http://localhost:5173")

    assert "http://localhost:5173" in settings.all_cors_origins
    assert "http://127.0.0.1:5173" in settings.all_cors_origins


def test_local_cors_origins_include_loopback_alias_for_configured_origins() -> None:
    settings = _make_settings(
        frontend_host="http://frontend.test",
        backend_cors_origins=["http://127.0.0.1:5173"],
    )

    assert "http://127.0.0.1:5173" in settings.all_cors_origins
    assert "http://localhost:5173" in settings.all_cors_origins


def test_rate_limiting_defaults_off_for_local_environment() -> None:
    settings = _make_settings(frontend_host="http://localhost:5173")

    assert settings.RATE_LIMITING_ENABLED is False


def test_rate_limiting_defaults_on_for_production_environment() -> None:
    settings = _make_settings(
        frontend_host="https://signalloop.example",
        environment="production",
    )

    assert settings.RATE_LIMITING_ENABLED is True


def test_database_tls_defaults_preserve_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_SSLMODE", raising=False)
    settings = _make_settings(frontend_host="http://localhost:5173")

    assert settings.POSTGRES_SSLMODE is None
    assert urlsplit(str(settings.SQLALCHEMY_DATABASE_URI)).query == ""


@pytest.mark.parametrize(
    "sslmode", ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
)
def test_database_tls_mode_is_included_in_connection_uri(
    monkeypatch: pytest.MonkeyPatch, sslmode: str,
) -> None:
    monkeypatch.setenv("POSTGRES_SSLMODE", sslmode)
    settings = _make_settings(frontend_host="http://localhost:5173")

    assert parse_qs(urlsplit(str(settings.SQLALCHEMY_DATABASE_URI)).query) == {
        "sslmode": [sslmode],
    }


def test_database_tls_mode_rejects_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_SSLMODE", "invalid-mode")

    with pytest.raises(ValidationError, match="POSTGRES_SSLMODE"):
        _make_settings(frontend_host="http://localhost:5173")


def test_empty_database_tls_mode_preserves_local_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_SSLMODE", "")
    settings = _make_settings(frontend_host="http://localhost:5173")

    assert settings.POSTGRES_SSLMODE is None
    assert urlsplit(str(settings.SQLALCHEMY_DATABASE_URI)).query == ""


def test_database_tls_mode_reaches_psycopg_connection_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_SSLMODE", "verify-full")
    settings = _make_settings(frontend_host="http://localhost:5173")
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    try:
        _, connection_arguments = engine.dialect.create_connect_args(engine.url)
        assert connection_arguments["sslmode"] == "verify-full"
    finally:
        engine.dispose()
