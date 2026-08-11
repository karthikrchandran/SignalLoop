"""Unit tests for the capability-aware provider registry."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.encryption import encrypt
from app.domain_models import (
    NotificationProvider,
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
)
from app.infrastructure.providers import registry as reg
from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.sendgrid import SendGridAdapter
from app.infrastructure.providers.smtp_email import SmtpEmailAdapter
from app.infrastructure.providers.twilio_sms import TwilioSmsAdapter
from app.infrastructure.providers.vapi_voice import VapiVoiceAdapter
from app.infrastructure.providers.whisper_stt import FasterWhisperLocalAdapter


class _FakeEmail(EmailAdapter):
    async def send_email(self, **kwargs):  # pragma: no cover - not exercised
        return {"status_code": 250}


def test_get_adapter_uses_default_when_no_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """No WorkspaceProviderSelection row -> default_factory short-circuit."""
    monkeypatch.setattr(reg, "get_workspace_provider_selection", lambda *a, **k: None)
    sentinel = _FakeEmail()
    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.email,
        default_factory=lambda: sentinel,
    )
    assert out is sentinel


def test_get_adapter_uses_explicit_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """A selection row triggers full resolution via the factory map."""
    monkeypatch.setattr(
        reg, "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.smtp,
    )
    monkeypatch.setattr(
        reg, "resolve_provider_credentials",
        lambda *a, **k: {
            "host": "smtp.example.com",
            "port": 587,
            "from_email": "from@example.com",
        },
    )

    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.email,
        default_factory=None,
    )
    assert isinstance(out, SmtpEmailAdapter)


def test_get_adapter_falls_back_to_default_on_factory_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the resolved factory blows up and a default exists, use the default."""
    monkeypatch.setattr(
        reg, "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.smtp,
    )
    # Missing required fields -> SmtpEmailAdapter raises ProviderConfigurationError.
    monkeypatch.setattr(reg, "resolve_provider_credentials", lambda *a, **k: {})

    sentinel = _FakeEmail()
    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.email,
        default_factory=lambda: sentinel,
    )
    assert out is sentinel


def test_get_adapter_reraises_when_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        reg, "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.smtp,
    )
    monkeypatch.setattr(reg, "resolve_provider_credentials", lambda *a, **k: {})

    with pytest.raises(ProviderConfigurationError):
        reg.get_adapter(
            MagicMock(),
            workspace_id="ws1",
            capability=ProviderCapability.email,
            default_factory=None,
        )


def test_get_strict_adapter_requires_explicit_workspace_selection() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[WorkspaceProviderSelection.__table__, ProviderCredential.__table__]
    )

    with Session(engine) as session:
        with pytest.raises(reg.ProviderResolutionError, match="No active provider selection"):
            reg.get_strict_adapter(
                session,
                workspace_id="ws1",
                capability=ProviderCapability.email,
            )


def test_get_strict_adapter_requires_active_stored_credential() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[WorkspaceProviderSelection.__table__, ProviderCredential.__table__]
    )

    with Session(engine) as session:
        session.add(
            WorkspaceProviderSelection(
                workspace_id="ws1",
                capability=ProviderCapability.email,
                provider=NotificationProvider.sendgrid,
            )
        )
        session.commit()

        with pytest.raises(reg.ProviderResolutionError, match="No active credentials"):
            reg.get_strict_adapter(
                session,
                workspace_id="ws1",
                capability=ProviderCapability.email,
            )


def test_get_strict_adapter_uses_active_encrypted_credential() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[WorkspaceProviderSelection.__table__, ProviderCredential.__table__]
    )

    with Session(engine) as session:
        session.add(
            WorkspaceProviderSelection(
                workspace_id="ws1",
                capability=ProviderCapability.email,
                provider=NotificationProvider.sendgrid,
            )
        )
        session.add(
            ProviderCredential(
                workspace_id="ws1",
                provider=NotificationProvider.sendgrid,
                channel="email",
                encrypted_api_key=encrypt("SG.enterprise"),
                config_json={"from_email": "from@example.com"},
            )
        )
        session.commit()

        out = reg.get_strict_adapter(
            session,
            workspace_id="ws1",
            capability=ProviderCapability.email,
        )

    assert isinstance(out, SendGridAdapter)
    assert out._api_key == "SG.enterprise"
    assert out._from_email == "from@example.com"


def test_build_adapter_from_credential_bypasses_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_adapter_from_credential`` ignores selection rows."""
    captured: dict = {}

    def fake_creds(_session, **kwargs):
        captured.update(kwargs)
        return {
            "api_key": "SG.x",
            "from_email": "from@example.com",
        }

    monkeypatch.setattr(reg, "resolve_provider_credentials", fake_creds)

    out = reg.build_adapter_from_credential(
        MagicMock(),
        workspace_id="ws1",
        provider=NotificationProvider.sendgrid,
        capability=ProviderCapability.email,
    )
    assert isinstance(out, SendGridAdapter)
    assert captured["workspace_id"] == "ws1"
    assert captured["provider"] == NotificationProvider.sendgrid
    assert captured["channel"] == "email"


def test_build_adapter_from_credential_unknown_pair_raises() -> None:
    """An unmapped (provider, capability) pair raises ProviderResolutionError."""
    with pytest.raises(reg.ProviderResolutionError):
        reg.build_adapter_from_credential(
            MagicMock(),
            workspace_id="ws1",
            provider=NotificationProvider.sendgrid,
            capability=ProviderCapability.voice,
        )


def test_get_adapter_resolves_faster_whisper_stt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reg,
        "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.faster_whisper_local,
    )
    monkeypatch.setattr(
        reg,
        "resolve_provider_credentials",
        lambda *a, **k: {
            "base_url": "http://stt:9000",
            "model": "base",
        },
    )

    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.stt,
        default_factory=None,
    )

    assert isinstance(out, FasterWhisperLocalAdapter)


def test_get_adapter_resolves_twilio_sms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reg,
        "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.twilio,
    )
    monkeypatch.setattr(
        reg,
        "resolve_provider_credentials",
        lambda *a, **k: {
            "account_sid": "AC123",
            "auth_token": "token",
            "phone_number": "+15551234567",
        },
    )

    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.sms,
        default_factory=None,
    )

    assert isinstance(out, TwilioSmsAdapter)


def test_get_adapter_resolves_vapi_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reg,
        "get_workspace_provider_selection",
        lambda *a, **k: NotificationProvider.vapi,
    )
    monkeypatch.setattr(
        reg,
        "resolve_provider_credentials",
        lambda *a, **k: {
            "api_key": "vapi-key",
            "phone_number_id": "phone-123",
            "assistant_id": "assistant-123",
        },
    )

    out = reg.get_adapter(
        MagicMock(),
        workspace_id="ws1",
        capability=ProviderCapability.voice,
        default_factory=None,
    )

    assert isinstance(out, VapiVoiceAdapter)
    assert out._phone_number_id == "phone-123"
    assert out._assistant_id == "assistant-123"


def test_provider_catalog_covers_every_capability() -> None:
    """PROVIDER_CATALOG should expose at least one option per capability."""
    for cap in ProviderCapability:
        assert cap.value in reg.PROVIDER_CATALOG
        assert len(reg.PROVIDER_CATALOG[cap.value]) >= 1
        for entry in reg.PROVIDER_CATALOG[cap.value]:
            assert "provider" in entry and "label" in entry


def test_provider_catalog_includes_local_stt_option() -> None:
    stt_providers = {
        entry["provider"]: entry
        for entry in reg.PROVIDER_CATALOG[ProviderCapability.stt.value]
    }

    local = stt_providers[NotificationProvider.faster_whisper_local.value]
    assert local["requires_creds"] is False
    assert local["local"] is True


def test_provider_catalog_includes_local_ollama_option() -> None:
    llm_providers = {
        entry["provider"]: entry
        for entry in reg.PROVIDER_CATALOG[ProviderCapability.llm.value]
    }

    local = llm_providers[NotificationProvider.ollama_local.value]
    assert local["requires_creds"] is False
    assert local["local"] is True


def test_provider_catalog_includes_vapi_voice_option() -> None:
    voice_providers = {
        entry["provider"]: entry
        for entry in reg.PROVIDER_CATALOG[ProviderCapability.voice.value]
    }

    vapi = voice_providers[NotificationProvider.vapi.value]
    assert vapi["requires_creds"] is True
    assert vapi["local"] is False
