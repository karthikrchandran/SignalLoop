"""Module: ``config``."""

import secrets
import warnings
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AnyUrl,
    BeforeValidator,
    EmailStr,
    HttpUrl,
    PostgresDsn,
    computed_field,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


def parse_cors(v: Any) -> list[str] | str:
    """Parse cors."""
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",") if i.strip()]
    elif isinstance(v, list | str):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    """Application settings."""
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[4] / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    FRONTEND_HOST: str = "http://localhost:5173"
    SERVER_HOST: str = "localhost:8001"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    RATE_LIMITING_ENABLED: bool | None = None

    BACKEND_CORS_ORIGINS: Annotated[
        list[AnyUrl] | str, BeforeValidator(parse_cors)
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def all_cors_origins(self) -> list[str]:
        """All cors origins."""
        origins = [str(origin).rstrip("/") for origin in self.BACKEND_CORS_ORIGINS]
        origins.append(self.FRONTEND_HOST.rstrip("/"))

        if self.ENVIRONMENT == "local":
            local_aliases = [
                alias
                for origin in origins
                for alias in [self._local_cors_origin_alias(origin)]
                if alias
            ]
            origins.extend(local_aliases)

        return list(dict.fromkeys(origins))

    @staticmethod
    def _local_cors_origin_alias(origin: str) -> str | None:
        replacements = (
            ("http://localhost:", "http://127.0.0.1:"),
            ("https://localhost:", "https://127.0.0.1:"),
            ("http://127.0.0.1:", "http://localhost:"),
            ("https://127.0.0.1:", "https://localhost:"),
        )
        for source, target in replacements:
            if origin.startswith(source):
                return target + origin.removeprefix(source)
        return None

    PROJECT_NAME: str
    SENTRY_DSN: HttpUrl | None = None
    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    REDIS_URL: str = "redis://redis:6379/0"
    DEFAULT_WORKSPACE_ID: str = "default"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        """Sqlalchemy database uri."""
        return PostgresDsn.build(
            scheme="postgresql+psycopg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )

    SMTP_TLS: bool = True
    SMTP_SSL: bool = False
    SMTP_PORT: int = 587
    SMTP_HOST: str | None = None
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAILS_FROM_EMAIL: EmailStr | None = None
    EMAILS_FROM_NAME: str | None = None
    SMTP_USERNAME: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str | None = None
    SMTP_USE_TLS: bool = False
    SMTP_USE_STARTTLS: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:1b"
    FASTER_WHISPER_BASE_URL: str = "http://localhost:9000"
    FASTER_WHISPER_MODEL: str = "base"

    @model_validator(mode="after")
    def _set_default_rate_limiting(self) -> Self:
        if self.RATE_LIMITING_ENABLED is None:
            self.RATE_LIMITING_ENABLED = self.ENVIRONMENT != "local"
        return self

    @model_validator(mode="after")
    def _set_default_emails_from(self) -> Self:
        if not self.EMAILS_FROM_NAME:
            self.EMAILS_FROM_NAME = self.PROJECT_NAME
        return self

    @model_validator(mode="after")
    def _sync_smtp_aliases(self) -> Self:
        if self.SMTP_USERNAME is None and self.SMTP_USER is not None:
            self.SMTP_USERNAME = self.SMTP_USER
        if self.SMTP_FROM_EMAIL is None and self.EMAILS_FROM_EMAIL is not None:
            self.SMTP_FROM_EMAIL = str(self.EMAILS_FROM_EMAIL)
        if self.SMTP_FROM_NAME is None and self.EMAILS_FROM_NAME is not None:
            self.SMTP_FROM_NAME = self.EMAILS_FROM_NAME
        return self

    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48

    @computed_field  # type: ignore[prop-decorator]
    @property
    def emails_enabled(self) -> bool:
        """Emails enabled."""
        return bool(self.SMTP_HOST and self.EMAILS_FROM_EMAIL)

    EMAIL_TEST_USER: EmailStr = "test@example.com"
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: str
    SENDGRID_API_KEY: str = ""
    SENDGRID_WEBHOOK_SECRET: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    ECRM_SHARED_API_BASE_URL: str = "http://localhost:5050"
    ECRM_SHARED_API_TOKEN: str = ""
    # Route-adapter cutover flag; intentionally unused by the low-level client.
    USE_ECRM_SHARED_RECORDS: bool = True
    USE_LOCAL_SHARED_RECORDS: bool = False
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    VAPI_API_KEY: str = ""
    VAPI_PHONE_NUMBER_ID: str = ""
    VAPI_ASSISTANT_ID: str = ""
    VAPI_API_BASE_URL: str = "https://api.vapi.ai"
    VAPI_CALL_ENDPOINT: str = "/call"
    DEEPGRAM_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    TEAM_NOTIFICATION_EMAIL: str = ""
    CALENDLY_WEBHOOK_SIGNING_KEY: str = ""
    CALENDLY_STATE_TTL_SECONDS: int = 24 * 60 * 60
    CALENDLY_WEBHOOK_MAX_AGE_SECONDS: int = 5 * 60
    MAX_RETRY_COUNT: int = 3  # Dead-letter retry cap (Story 5.3)
    AUTH_MODE: Literal["oidc", "local-test"] = "local-test"
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = ""
    OIDC_AUDIENCE: str = ""
    OIDC_SCOPES: str = "openid profile email"
    OIDC_TRANSACTION_TTL_SECONDS: int = 300
    TENANT_PUBLIC_HOSTS: str = "ara.localhost=ara-global,ai-consulting.localhost=ai-consulting"
    TRUSTED_PROXY_CIDRS: str = ""
    TRUSTED_ENTRY_ORIGINS: str = ""

    def _check_default_secret(self, var_name: str, value: str | None) -> None:
        if value == "changethis":
            message = (
                f'The value of {var_name} is "changethis", '
                "for security, please change it, at least for deployments."
            )
            if self.ENVIRONMENT == "local":
                warnings.warn(message, stacklevel=1)
            else:
                raise ValueError(message)

    @model_validator(mode="after")
    def _enforce_non_default_secrets(self) -> Self:
        self._check_default_secret("SECRET_KEY", self.SECRET_KEY)
        self._check_default_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        self._check_default_secret(
            "FIRST_SUPERUSER_PASSWORD", self.FIRST_SUPERUSER_PASSWORD
        )

        return self


settings = Settings()  # type: ignore
