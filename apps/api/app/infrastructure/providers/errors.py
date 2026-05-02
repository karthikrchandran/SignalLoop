"""Shared provider adapter errors."""
from __future__ import annotations


class ProviderConfigurationError(RuntimeError):
    """Raised when a required provider credential is not configured."""


def require_provider_key(value: str | None, setting_name: str) -> str:
    """Return a non-empty provider key or raise a sanitized config error."""
    key = (value or "").strip()
    if not key:
        raise ProviderConfigurationError(f"{setting_name} is not configured")
    return key