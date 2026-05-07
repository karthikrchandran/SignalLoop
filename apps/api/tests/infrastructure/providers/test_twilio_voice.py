"""Unit tests for ``app.infrastructure.providers.twilio_voice``.

Covers credential fallback, successful initiate_call payload, error path,
twilio error-code parsing (with/without JSON body), and HMAC-SHA1
signature verification including negative paths.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
from base64 import b64encode
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.infrastructure.providers import twilio_voice as tw_mod
from app.infrastructure.providers.twilio_voice import (
    TWILIO_API_BASE,
    TwilioVoiceAdapter,
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
    monkeypatch.setattr(tw_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_init_uses_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor falls back to settings credentials when none provided."""
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC1")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "tok")
    monkeypatch.setattr(settings, "TWILIO_PHONE_NUMBER", "+15550000000")
    a = TwilioVoiceAdapter()
    assert a._account_sid == "AC1"
    assert a._auth_token == "tok"
    assert a._from_number == "+15550000000"


def test_init_uses_explicit_args() -> None:
    """Explicit credentials override settings."""
    a = TwilioVoiceAdapter(account_sid="X", auth_token="Y", from_number="+1")
    assert (a._account_sid, a._auth_token, a._from_number) == ("X", "Y", "+1")


def test_initiate_call_success_returns_sid_and_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """201 returns parsed call_sid and status; payload includes machine detection."""
    resp = MagicMock(status_code=201)
    resp.json.return_value = {"sid": "CA1", "status": "queued"}
    client = _Client(resp)
    _patch(monkeypatch, client)

    a = TwilioVoiceAdapter(account_sid="AC", auth_token="t", from_number="+1")
    out = _run(a.initiate_call(
        to="+19990001111",
        twiml_url="https://e.io/twiml",
        status_callback_url="https://e.io/status",
    ))
    assert out == {"call_sid": "CA1", "status": "queued"}
    call = client.calls[0]
    assert call["url"] == f"{TWILIO_API_BASE}/Accounts/AC/Calls.json"
    assert call["auth"] == ("AC", "t")
    assert call["data"]["To"] == "+19990001111"
    assert call["data"]["From"] == "+1"
    assert call["data"]["MachineDetection"] == "Enable"
    assert call["data"]["Record"] == "true"
    assert call["data"]["RecordingStatusCallback"] == "https://e.io/recording"


def test_initiate_call_failure_returns_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-2xx response returns the error envelope with parsed twilio code."""
    resp = MagicMock(status_code=400)
    resp.json.return_value = {"code": 21610, "message": "blocked"}
    _patch(monkeypatch, _Client(resp))

    a = TwilioVoiceAdapter(account_sid="AC", auth_token="t", from_number="+1")
    out = _run(a.initiate_call(
        to="+1", twiml_url="https://e.io/t",
        status_callback_url="https://e.io/status",
    ))
    assert out == {
        "call_sid": "",
        "status": "failed",
        "error": "twilio_call_failed",
        "error_code": "21610",
    }


def test_initiate_call_failure_with_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid JSON error body falls back to ``http_error`` code."""
    resp = MagicMock(status_code=500)
    resp.json.side_effect = ValueError("bad")
    _patch(monkeypatch, _Client(resp))

    a = TwilioVoiceAdapter(account_sid="AC", auth_token="t", from_number="+1")
    out = _run(a.initiate_call(
        to="+1", twiml_url="https://e.io/t",
        status_callback_url="https://e.io/status",
    ))
    assert out["error_code"] == "http_error"


def test_twilio_error_code_no_code_field() -> None:
    """JSON body without a code field returns the generic twilio_error code."""
    resp = MagicMock()
    resp.json.return_value = {"message": "x"}
    assert _twilio_error_code(resp) == "twilio_error"


def test_verify_signature_returns_false_when_token_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing auth token short-circuits to False."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "")
    assert TwilioVoiceAdapter.verify_request_signature(
        "https://e.io/x", {"a": "1"}, "sig",
    ) is False


def test_verify_signature_returns_false_when_signature_missing() -> None:
    """Empty signature short-circuits to False even with a token."""
    assert TwilioVoiceAdapter.verify_request_signature(
        "https://e.io/x", {"a": "1"}, "", auth_token="tok",
    ) is False


def test_verify_signature_valid_signature_returns_true() -> None:
    """Correctly computed HMAC-SHA1 base64 signature passes verification."""
    url = "https://e.io/x"
    params = {"b": "2", "a": "1"}
    data_string = url + "".join(f"{k}{v}" for k, v in sorted(params.items()))
    expected = b64encode(
        hmac.new(b"tok", data_string.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    assert TwilioVoiceAdapter.verify_request_signature(
        url, params, expected, auth_token="tok",
    ) is True


def test_verify_signature_invalid_signature_returns_false() -> None:
    """Wrong signature is rejected."""
    assert TwilioVoiceAdapter.verify_request_signature(
        "https://e.io/x", {"a": "1"}, "deadbeef", auth_token="tok",
    ) is False


def test_verify_signature_uses_settings_token_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When auth_token is not passed, settings.TWILIO_AUTH_TOKEN is used."""
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "from_settings")
    url = "https://e.io/x"
    params = {"a": "1"}
    data_string = url + "a1"
    expected = b64encode(
        hmac.new(b"from_settings", data_string.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    assert TwilioVoiceAdapter.verify_request_signature(
        url, params, expected,
    ) is True
