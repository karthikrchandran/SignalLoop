"""Unit tests for provider-selection catalog validation."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routes.provider_credentials import (
    _ensure_provider_supported_for_capability,
)
from app.domain_models import NotificationProvider, ProviderCapability


def test_provider_selection_validation_allows_catalog_pair() -> None:
    _ensure_provider_supported_for_capability(
        ProviderCapability.email,
        NotificationProvider.smtp,
    )


def test_provider_selection_validation_rejects_enum_only_pair() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _ensure_provider_supported_for_capability(
            ProviderCapability.email,
            NotificationProvider.elevenlabs,
        )

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail["error"]
    assert detail["code"] == "UNSUPPORTED_PROVIDER_CAPABILITY"
    assert detail["details"]["capability"] == "email"
    assert detail["details"]["provider"] == "elevenlabs"
    assert "smtp" in detail["details"]["supported_providers"]
