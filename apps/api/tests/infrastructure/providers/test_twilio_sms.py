"""Unit tests for ``app.infrastructure.providers.twilio_sms``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.infrastructure.providers import twilio_sms as sms_mod
from app.infrastructure.providers.twilio_sms import (
    TWILIO_API_BASE,
    TwilioSmsAdapter,
    _twilio_error_code,
)


def _run(coro):
    return asyncio.run(coro)


class _Client:
    """Async context manager replacement for ``httpx.AsyncClient``."""

    def __init__(self, response: Any) -> None:
        self._r = response
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *a, **k):  # pragma: no cover
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, data=None, auth=None, **kwargs):
        self.calls.append({"url": url, "data": data, "auth": auth})
        return self._r


def _patch(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    monkeypatch.setattr(sms_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_init_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15550000000")

    adapter = TwilioSmsAdapter()

    assert adapter._account_sid == "AC1"
    assert adapter._auth_token == "tok"
    assert adapter._from_number == "+15550000000"


def test_send_sms_success_returns_sid_and_status(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=201)
    resp.json.return_value = {"sid": "SM1", "status": "queued"}
    client = _Client(resp)
    _patch(monkeypatch, client)

    adapter = TwilioSmsAdapter(account_sid="AC", auth_token="t", from_number="+1")
    out = _run(adapter.send_sms(to="+19990001111", message="Hello"))

    assert out == {"status_code": 201, "message_sid": "SM1", "status": "queued"}
    call = client.calls[0]
    assert call["url"] == f"{TWILIO_API_BASE}/Accounts/AC/Messages.json"
    assert call["auth"] == ("AC", "t")
    assert call["data"] == {
        "To": "+19990001111",
        "From": "+1",
        "Body": "Hello",
    }


def test_send_sms_failure_returns_error_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=400)
    resp.json.return_value = {"code": 21610, "message": "blocked"}
    _patch(monkeypatch, _Client(resp))

    adapter = TwilioSmsAdapter(account_sid="AC", auth_token="t", from_number="+1")
    out = _run(adapter.send_sms(to="+1", message="Hello"))

    assert out == {
        "status_code": 400,
        "message_sid": "",
        "status": "failed",
        "error": "twilio_sms_failed",
        "error_code": "21610",
    }


def test_twilio_error_code_handles_invalid_json() -> None:
    resp = MagicMock()
    resp.json.side_effect = ValueError("bad json")

    assert _twilio_error_code(resp) == "http_error"
