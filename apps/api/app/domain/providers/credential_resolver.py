"""Credential resolver for workers and adapters.

Workers should call :func:`resolve_provider_credentials` instead of reading
``settings.*`` directly.  Resolution order:

1. Active row in ``provider_credentials`` for (workspace_id, provider, channel)
   → decrypt the stored key(s) and return them.
2. Fall back to application settings (``settings.SENDGRID_API_KEY``, etc.)
   so single-tenant / demo deployments work with just ``.env`` values.

Example::

    from app.domain.providers.credential_resolver import resolve_provider_credentials
    from app.domain_models import NotificationProvider

    creds = resolve_provider_credentials(
        session, workspace_id="ws-acme", provider=NotificationProvider.sendgrid, channel="email"
    )
    # creds → {"api_key": "SG.xxx", "from_email": "no-reply@acme.com"}
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.encryption import decrypt
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
)


def resolve_provider_credentials(
    session: Session,
    workspace_id: str,
    provider: NotificationProvider,
    channel: str,
) -> dict[str, Any]:
    """Return decrypted credentials for *provider*/*channel* in *workspace_id*.

    The returned dict always contains at least ``api_key``.  Extra keys are
    provider-specific and sourced from ``config_json`` stored alongside the
    credential row.

    Falls back to ``settings`` when no active DB row exists, enabling the
    single-tenant demo to work from ``.env`` without any DB rows.
    """
    row = session.exec(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider == provider,
            ProviderCredential.channel == channel,
            ProviderCredential.is_active == True,  # noqa: E712
        )
    ).first()

    if row:
        creds: dict[str, Any] = {
            "api_key": decrypt(row.encrypted_api_key),
        }
        if row.encrypted_api_secret:
            creds["api_secret"] = decrypt(row.encrypted_api_secret)
        # Merge any extra config (e.g. from_email, phone_number, account_sid)
        creds.update(row.config_json)
        return creds

    # -----------------------------------------------------------------------
    # Fallback: read from application settings (.env)
    # -----------------------------------------------------------------------
    return _settings_fallback(provider, channel)


def _settings_fallback(provider: NotificationProvider, channel: str) -> dict[str, Any]:
    """Return credentials from settings for single-tenant / demo mode."""
    if provider == NotificationProvider.sendgrid:
        return {
            "api_key": settings.SENDGRID_API_KEY,
            "from_email": settings.SENDGRID_FROM_EMAIL,
            "webhook_secret": settings.SENDGRID_WEBHOOK_SECRET,
        }

    if provider == NotificationProvider.twilio:
        if channel == "voice":
            return {
                "api_key": settings.TWILIO_ACCOUNT_SID,   # primary identifier
                "api_secret": settings.TWILIO_AUTH_TOKEN,
                "account_sid": settings.TWILIO_ACCOUNT_SID,
                "auth_token": settings.TWILIO_AUTH_TOKEN,
                "phone_number": settings.TWILIO_PHONE_NUMBER,
            }
        # SMS also uses Twilio credentials
        return {
            "api_key": settings.TWILIO_ACCOUNT_SID,
            "api_secret": settings.TWILIO_AUTH_TOKEN,
            "account_sid": settings.TWILIO_ACCOUNT_SID,
            "auth_token": settings.TWILIO_AUTH_TOKEN,
            "phone_number": settings.TWILIO_PHONE_NUMBER,
        }

    if provider == NotificationProvider.vapi:
        return {
            "api_key": settings.VAPI_API_KEY,
            "phone_number_id": settings.VAPI_PHONE_NUMBER_ID,
            "assistant_id": settings.VAPI_ASSISTANT_ID,
            "base_url": settings.VAPI_API_BASE_URL,
            "call_endpoint": settings.VAPI_CALL_ENDPOINT,
        }

    if provider == NotificationProvider.deepgram:
        return {"api_key": getattr(settings, "DEEPGRAM_API_KEY", "") or ""}

    if provider == NotificationProvider.groq:
        return {"api_key": getattr(settings, "GROQ_API_KEY", "") or ""}

    if provider == NotificationProvider.openai:
        return {
            "api_key": getattr(settings, "OPENAI_API_KEY", "") or "",
            "base_url": getattr(settings, "OPENAI_BASE_URL", "") or "",
            "model": getattr(settings, "OPENAI_MODEL", "") or "",
        }

    if provider == NotificationProvider.ollama_local:
        return {
            "base_url": settings.OLLAMA_BASE_URL,
            "model": settings.OLLAMA_MODEL,
        }

    if provider == NotificationProvider.faster_whisper_local:
        return {
            "base_url": settings.FASTER_WHISPER_BASE_URL,
            "model": settings.FASTER_WHISPER_MODEL,
        }

    if provider == NotificationProvider.smtp:
        return {
            "host": settings.SMTP_HOST or "",
            "port": settings.SMTP_PORT or 587,
            "username": settings.SMTP_USERNAME or settings.SMTP_USER or "",
            "password": settings.SMTP_PASSWORD or "",
            "from_email": settings.SMTP_FROM_EMAIL
            or str(settings.EMAILS_FROM_EMAIL or ""),
            "from_name": settings.SMTP_FROM_NAME or settings.EMAILS_FROM_NAME or "",
            "use_tls": settings.SMTP_USE_TLS,
            "use_starttls": settings.SMTP_USE_STARTTLS,
        }

    # Generic fallback — return empty dict so callers can decide what to do
    return {}


# ---------------------------------------------------------------------------
# Active-provider selection (capability → provider) per workspace
# ---------------------------------------------------------------------------

# Default provider per capability when no WorkspaceProviderSelection row exists.
_DEFAULT_PROVIDER_BY_CAPABILITY: dict[ProviderCapability, NotificationProvider] = {
    ProviderCapability.email: NotificationProvider.sendgrid,
    ProviderCapability.sms: NotificationProvider.twilio,
    ProviderCapability.voice: NotificationProvider.twilio,
    ProviderCapability.stt: NotificationProvider.deepgram,
    ProviderCapability.tts: NotificationProvider.deepgram,
    ProviderCapability.llm: NotificationProvider.groq,
}


def resolve_active_provider(
    session: Session,
    workspace_id: str,
    capability: ProviderCapability,
) -> NotificationProvider:
    """Return the provider currently selected for *capability* in *workspace_id*.

    Falls back to a built-in default (SendGrid/Twilio/Deepgram/Groq) when no
    row exists, preserving the original single-tenant behaviour.
    """
    row = session.exec(
        select(WorkspaceProviderSelection).where(
            WorkspaceProviderSelection.workspace_id == workspace_id,
            WorkspaceProviderSelection.capability == capability,
            WorkspaceProviderSelection.is_active == True,  # noqa: E712
        )
    ).first()
    if row:
        return row.provider
    return _DEFAULT_PROVIDER_BY_CAPABILITY[capability]


def get_workspace_provider_selection(
    session: Session,
    workspace_id: str,
    capability: ProviderCapability,
) -> NotificationProvider | None:
    """Return the explicitly-selected provider for *capability*, else None.

    Unlike :func:`resolve_active_provider` this does **not** apply a default —
    callers use it to detect whether the workspace has opted into the new
    multi-provider behaviour.  When ``None`` is returned, legacy callers
    should keep instantiating their hard-coded default adapter so existing
    tests that patch e.g. ``SendGridAdapter`` continue to work.
    """
    row = session.exec(
        select(WorkspaceProviderSelection).where(
            WorkspaceProviderSelection.workspace_id == workspace_id,
            WorkspaceProviderSelection.capability == capability,
            WorkspaceProviderSelection.is_active == True,  # noqa: E712
        )
    ).first()
    return row.provider if row else None
