"""Tests for provider credential settings fallbacks."""
from __future__ import annotations

from app.core.config import settings
from app.domain.providers import credential_resolver as resolver
from app.domain_models import NotificationProvider


def test_settings_fallback_returns_faster_whisper_config(monkeypatch) -> None:
    monkeypatch.setattr(
        settings,
        "FASTER_WHISPER_BASE_URL",
        "http://stt:9000",
    )
    monkeypatch.setattr(settings, "FASTER_WHISPER_MODEL", "small")

    creds = resolver._settings_fallback(
        NotificationProvider.faster_whisper_local,
        "voice",
    )

    assert creds == {
        "base_url": "http://stt:9000",
        "model": "small",
    }


def test_settings_fallback_returns_ollama_config(monkeypatch) -> None:
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://ollama:11434")
    monkeypatch.setattr(settings, "OLLAMA_MODEL", "llama3.2:1b")

    creds = resolver._settings_fallback(
        NotificationProvider.ollama_local,
        "voice",
    )

    assert creds == {
        "base_url": "http://ollama:11434",
        "model": "llama3.2:1b",
    }
