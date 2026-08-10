"""Workspace-scoped runtime setting resolution helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, select

from app.core.config import settings
from app.core.encryption import decrypt
from app.domain_models import WorkspaceRuntimeConfig

RuntimeSettingSource = Literal["database", "environment", "missing"]


@dataclass(frozen=True)
class ResolvedRuntimeValue:
    value: str
    source: RuntimeSettingSource

    @property
    def configured(self) -> bool:
        return bool(self.value)


@dataclass(frozen=True)
class ResolvedWorkspaceRuntimeConfig:
    deepgram_api_key: ResolvedRuntimeValue
    groq_api_key: ResolvedRuntimeValue
    team_notification_email: ResolvedRuntimeValue


def resolve_workspace_runtime_config(
    session: Session,
    workspace_id: str,
) -> ResolvedWorkspaceRuntimeConfig:
    """Resolve runtime settings from workspace overrides or app settings."""

    row = session.exec(
        select(WorkspaceRuntimeConfig).where(WorkspaceRuntimeConfig.workspace_id == workspace_id)
    ).first()
    if not isinstance(row, WorkspaceRuntimeConfig):
        row = None

    return ResolvedWorkspaceRuntimeConfig(
        deepgram_api_key=_resolve_secret_value(
            row.encrypted_deepgram_api_key if row else None,
            settings.DEEPGRAM_API_KEY,
        ),
        groq_api_key=_resolve_secret_value(
            row.encrypted_groq_api_key if row else None,
            settings.GROQ_API_KEY,
        ),
        team_notification_email=_resolve_plain_value(
            row.team_notification_email if row else None,
            (
                settings.TEAM_NOTIFICATION_EMAIL
                if workspace_id == settings.DEFAULT_WORKSPACE_ID
                else ""
            ),
        ),
    )


def resolve_team_notification_email(session: Session, workspace_id: str) -> str:
    """Return the effective team-notification email for a workspace."""

    return resolve_workspace_runtime_config(session, workspace_id).team_notification_email.value


def _resolve_secret_value(
    encrypted_value: str | None,
    fallback_value: str,
) -> ResolvedRuntimeValue:
    if isinstance(encrypted_value, str) and encrypted_value:
        try:
            decrypted = decrypt(encrypted_value).strip()
        except ValueError:
            decrypted = ""
        if decrypted:
            return ResolvedRuntimeValue(value=decrypted, source="database")

    fallback = fallback_value.strip()
    if fallback:
        return ResolvedRuntimeValue(value=fallback, source="environment")

    return ResolvedRuntimeValue(value="", source="missing")


def _resolve_plain_value(
    stored_value: str | None,
    fallback_value: str,
) -> ResolvedRuntimeValue:
    database_value = stored_value.strip() if isinstance(stored_value, str) else ""
    if database_value:
        return ResolvedRuntimeValue(value=database_value, source="database")

    fallback = fallback_value.strip()
    if fallback:
        return ResolvedRuntimeValue(value=fallback, source="environment")

    return ResolvedRuntimeValue(value="", source="missing")
