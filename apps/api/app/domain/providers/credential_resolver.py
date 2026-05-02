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
from app.domain_models import NotificationProvider, ProviderCredential


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

    # Generic fallback — return empty dict so callers can decide what to do
    return {}
