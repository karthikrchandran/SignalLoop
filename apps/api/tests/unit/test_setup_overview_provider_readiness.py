"""Unit tests for setup-overview provider readiness helpers."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.routes import utils
from app.domain.runtime_settings import ResolvedRuntimeValue
from app.domain_models import NotificationProvider, ProviderCapability


def _empty_runtime_config() -> SimpleNamespace:
    return SimpleNamespace(
        deepgram_api_key=ResolvedRuntimeValue(value="", source="missing"),
        groq_api_key=ResolvedRuntimeValue(value="", source="missing"),
        team_notification_email=ResolvedRuntimeValue(value="", source="missing"),
    )


def test_provider_capability_integration_reports_local_provider_selections(
    monkeypatch,
) -> None:
    selections = {
        ProviderCapability.email: NotificationProvider.smtp,
        ProviderCapability.stt: NotificationProvider.faster_whisper_local,
        ProviderCapability.llm: NotificationProvider.ollama_local,
    }
    creds = {
        NotificationProvider.smtp: {
            "host": "localhost",
            "port": 1025,
            "from_email": "demo@example.com",
        },
        NotificationProvider.faster_whisper_local: {
            "base_url": "http://localhost:9000",
            "model": "base",
        },
        NotificationProvider.ollama_local: {
            "base_url": "http://localhost:11434",
            "model": "llama3.2:1b",
        },
    }

    monkeypatch.setattr(
        utils,
        "resolve_active_provider",
        lambda _session, _workspace_id, capability: selections[capability],
    )
    monkeypatch.setattr(
        utils,
        "resolve_provider_credentials",
        lambda _session, *, provider, **_kwargs: creds[provider],
    )

    email = utils._provider_capability_integration(
        MagicMock(),
        "ws-local",
        ProviderCapability.email,
        credentials={},
        runtime_config=_empty_runtime_config(),
    )
    stt = utils._provider_capability_integration(
        MagicMock(),
        "ws-local",
        ProviderCapability.stt,
        credentials={},
        runtime_config=_empty_runtime_config(),
    )
    llm = utils._provider_capability_integration(
        MagicMock(),
        "ws-local",
        ProviderCapability.llm,
        credentials={},
        runtime_config=_empty_runtime_config(),
    )

    assert email.provider == NotificationProvider.smtp
    assert email.configured is True
    assert email.local is True
    assert email.config == {
        "host": "localhost",
        "port": "1025",
        "from_email": "demo@example.com",
    }
    assert stt.provider == NotificationProvider.faster_whisper_local
    assert stt.configured is True
    assert stt.local is True
    assert llm.provider == NotificationProvider.ollama_local
    assert llm.configured is True
    assert llm.local is True


def test_provider_capability_integration_marks_incomplete_smtp_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        utils,
        "resolve_active_provider",
        lambda _session, _workspace_id, _capability: NotificationProvider.smtp,
    )
    monkeypatch.setattr(
        utils,
        "resolve_provider_credentials",
        lambda *_args, **_kwargs: {"host": "", "from_email": ""},
    )

    integration = utils._provider_capability_integration(
        MagicMock(),
        "ws-local",
        ProviderCapability.email,
        credentials={},
        runtime_config=_empty_runtime_config(),
    )

    assert integration.provider == NotificationProvider.smtp
    assert integration.configured is False
    assert integration.source == "missing"
    assert integration.config == {}


def test_provider_capability_integration_reports_vapi_voice_selection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        utils,
        "resolve_active_provider",
        lambda _session, _workspace_id, _capability: NotificationProvider.vapi,
    )
    monkeypatch.setattr(
        utils,
        "resolve_provider_credentials",
        lambda *_args, **_kwargs: {
            "api_key": "vapi-key",
            "phone_number_id": "phone-123",
            "assistant_id": "assistant-123",
        },
    )

    integration = utils._provider_capability_integration(
        MagicMock(),
        "ws-vapi",
        ProviderCapability.voice,
        credentials={},
        runtime_config=_empty_runtime_config(),
    )

    assert integration.provider == NotificationProvider.vapi
    assert integration.configured is True
    assert integration.source == "environment"
    assert integration.local is False
    assert integration.config == {
        "phone_number_id": "phone-123",
        "assistant_id": "assistant-123",
    }
