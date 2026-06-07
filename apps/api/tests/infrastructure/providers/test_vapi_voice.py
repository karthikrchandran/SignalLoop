"""Unit tests for ``app.infrastructure.providers.vapi_voice``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import settings
from app.infrastructure.providers import vapi_voice as vapi_mod
from app.infrastructure.providers.vapi_voice import (
    VAPI_API_BASE_URL,
    VapiVoiceAdapter,
    _vapi_error_code,
)


def _run(coro):
    return asyncio.run(coro)


class _Client:
    """Async context manager replacement for ``httpx.AsyncClient``."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, headers=None, json=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def _patch(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    monkeypatch.setattr(vapi_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_init_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "VAPI_API_KEY", "settings-key")
    monkeypatch.setattr(settings, "VAPI_PHONE_NUMBER_ID", "phone-1")
    monkeypatch.setattr(settings, "VAPI_ASSISTANT_ID", "assistant-1")
    monkeypatch.setattr(settings, "VAPI_API_BASE_URL", "https://vapi.example")
    monkeypatch.setattr(settings, "VAPI_CALL_ENDPOINT", "/call/phone")

    adapter = VapiVoiceAdapter()

    assert adapter._api_key == "settings-key"
    assert adapter._phone_number_id == "phone-1"
    assert adapter._assistant_id == "assistant-1"
    assert adapter._call_url() == "https://vapi.example/call/phone"


def test_initiate_call_success_posts_create_call_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resp = MagicMock(status_code=201)
    resp.json.return_value = {"id": "call-123", "status": "queued"}
    client = _Client(resp)
    _patch(monkeypatch, client)

    adapter = VapiVoiceAdapter(
        api_key="vapi-key",
        phone_number_id="phone-123",
        assistant_id="assistant-123",
    )
    out = _run(
        adapter.initiate_call(
            to="+15551234567",
            twiml_url="https://example.com/twiml",
            status_callback_url="https://example.com/status",
            metadata={"lead_id": "lead-1"},
            assistant_overrides={"variableValues": {"first_name": "Ada"}},
        )
    )

    assert out == {
        "call_sid": "call-123",
        "provider_call_id": "call-123",
        "status": "queued",
        "provider": "vapi",
    }
    call = client.calls[0]
    assert call["url"] == f"{VAPI_API_BASE_URL}/call"
    assert call["headers"]["Authorization"] == "Bearer vapi-key"
    assert call["json"]["phoneNumberId"] == "phone-123"
    assert call["json"]["assistantId"] == "assistant-123"
    assert call["json"]["customer"] == {"number": "+15551234567"}
    assert call["json"]["metadata"] == {"lead_id": "lead-1"}
    assert call["json"]["assistantOverrides"] == {
        "variableValues": {"first_name": "Ada"}
    }


def test_initiate_call_missing_config_returns_failed_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _Client(MagicMock(status_code=201))
    _patch(monkeypatch, client)

    adapter = VapiVoiceAdapter(api_key="", phone_number_id="", assistant_id="")
    out = _run(adapter.initiate_call(to="+15551234567"))

    assert out["call_sid"] == ""
    assert out["status"] == "failed"
    assert out["provider"] == "vapi"
    assert out["error"] == "vapi_not_configured"
    assert out["error_code"] == "missing_api_key_phone_number_id_assistant_id"
    assert client.calls == []


def test_initiate_call_http_failure_sanitizes_error_code(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    resp = MagicMock(status_code=401)
    resp.json.return_value = {
        "error": {
            "code": "unauthorized",
            "message": "secret-token-should-not-log",
        }
    }
    _patch(monkeypatch, _Client(resp))
    adapter = VapiVoiceAdapter(
        api_key="secret-token-should-not-log",
        phone_number_id="phone-123",
        assistant_id="assistant-123",
    )

    out = _run(adapter.initiate_call(to="+15551234567"))

    assert out == {
        "call_sid": "",
        "status": "failed",
        "provider": "vapi",
        "error": "vapi_call_failed",
        "error_code": "unauthorized",
    }
    assert "secret-token-should-not-log" not in caplog.text


def test_initiate_call_request_exception_returns_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, _Client(httpx.ConnectError("network down")))
    adapter = VapiVoiceAdapter(
        api_key="vapi-key",
        phone_number_id="phone-123",
        assistant_id="assistant-123",
    )

    out = _run(adapter.initiate_call(to="+15551234567"))

    assert out["call_sid"] == ""
    assert out["status"] == "failed"
    assert out["error"] == "vapi_request_failed"
    assert out["error_code"] == "ConnectError"


def test_normalize_webhook_event_returns_canonical_fields() -> None:
    adapter = VapiVoiceAdapter(
        api_key="vapi-key",
        phone_number_id="phone-123",
        assistant_id="assistant-123",
    )

    out = _run(
        adapter.normalize_webhook_event(
            {
                "message": {
                    "id": "event-123",
                    "type": "end-of-call-report",
                    "call": {
                        "id": "call-123",
                        "status": "ended",
                        "recordingUrl": "https://recording.example",
                        "transcript": "Hello",
                    },
                }
            }
        )
    )

    assert out["event_type"] == "end-of-call-report"
    assert out["provider_event_id"] == "event-123"
    assert out["provider_call_id"] == "call-123"
    assert out["status"] == "ended"
    assert out["recording_url"] == "https://recording.example"
    assert out["transcript"] == "Hello"


def test_vapi_error_code_handles_invalid_json() -> None:
    resp = MagicMock()
    resp.json.side_effect = ValueError("bad json")

    assert _vapi_error_code(resp) == "vapi_error"
