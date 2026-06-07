from typing import Literal

from app.core.config import Settings


def _make_settings(
    *,
    frontend_host: str,
    backend_cors_origins: list[str] | None = None,
    environment: Literal["local", "staging", "production"] = "local",
) -> Settings:
    return Settings(
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
        frontend_host="https://engagehub.example",
        environment="production",
    )

    assert settings.RATE_LIMITING_ENABLED is True
