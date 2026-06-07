"""Unit tests for ``app.infrastructure.providers.sendgrid``.

Covers payload construction, retry on 429/5xx, non-retry on 4xx,
``HTTPError`` retry-then-raise behavior, webhook normalization and
HMAC-SHA256 signature verification (with and without configured secret).
All HTTP and ``asyncio.sleep`` calls are mocked.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import settings
from app.infrastructure.providers import sendgrid as sendgrid_mod
from app.infrastructure.providers.sendgrid import (
    MAX_RETRIES,
    SENDGRID_API_URL,
    SendGridAdapter,
)


def _run(coro):
    """Run an awaitable synchronously."""
    return asyncio.run(coro)


def _mk_response(status_code: int, headers: dict[str, str] | None = None,
                 text: str = "") -> MagicMock:
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = text
    return resp


class _FakeAsyncClient:
    """Async context manager replacement for ``httpx.AsyncClient``."""

    def __init__(self, responses: list[Any]) -> None:
        # ``responses`` may contain MagicMock responses or Exception instances
        # to raise on ``post``.
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *args, **kwargs):  # pragma: no cover - constructor noise
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers=None, json=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "json": json})
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: _FakeAsyncClient) -> None:
    monkeypatch.setattr(sendgrid_mod.httpx, "AsyncClient", lambda *a, **k: fake)


def test_init_uses_settings_when_no_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """Constructor falls back to settings values when none provided."""
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "settings-key")
    monkeypatch.setattr(settings, "SENDGRID_FROM_EMAIL", "from@s.io")
    a = SendGridAdapter()
    assert a._api_key == "settings-key"
    assert a._from_email == "from@s.io"


def test_init_uses_explicit_args() -> None:
    """Constructor honours explicit credentials over settings."""
    a = SendGridAdapter(api_key="k", from_email="e@x.io")
    assert a._api_key == "k"
    assert a._from_email == "e@x.io"


def test_send_email_success_returns_status_and_message_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """202 response returns parsed status and X-Message-Id header."""
    fake = _FakeAsyncClient([_mk_response(202, headers={"X-Message-Id": "msg-1"})])
    _patch_client(monkeypatch, fake)

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    result = _run(
        a.send_email(
            to="t@e.io", subject="s", body_html="<b>h</b>", body_text="t",
            idempotency_key="idem-1", reply_to="r@e.io",
            custom_args={"tag": "v"},
        )
    )

    assert result == {"status_code": 202, "message_id": "msg-1"}
    call = fake.calls[0]
    assert call["url"] == SENDGRID_API_URL
    assert call["headers"]["Authorization"] == "Bearer k"
    assert call["headers"]["X-Idempotency-Key"] == "idem-1"
    pers = call["json"]["personalizations"][0]
    assert pers["to"] == [{"email": "t@e.io"}]
    assert pers["custom_args"] == {"tag": "v"}
    assert call["json"]["from"] == {"email": "f@e.io"}
    assert call["json"]["reply_to"] == {"email": "r@e.io"}
    assert {"type": "text/plain", "value": "t"} in call["json"]["content"]
    assert {"type": "text/html", "value": "<b>h</b>"} in call["json"]["content"]


def test_send_email_omits_optional_fields_when_not_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No reply_to / custom_args / idempotency_key in payload when omitted."""
    fake = _FakeAsyncClient([_mk_response(200)])
    _patch_client(monkeypatch, fake)

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))

    call = fake.calls[0]
    assert "X-Idempotency-Key" not in call["headers"]
    assert "reply_to" not in call["json"]
    assert "custom_args" not in call["json"]["personalizations"][0]


def test_send_email_returns_empty_message_id_when_header_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing X-Message-Id returns empty string rather than raising."""
    fake = _FakeAsyncClient([_mk_response(201)])
    _patch_client(monkeypatch, fake)
    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))
    assert out["message_id"] == ""


def test_send_email_4xx_client_error_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400 response is returned immediately without retry."""
    fake = _FakeAsyncClient([_mk_response(400, text="bad")])
    _patch_client(monkeypatch, fake)
    sleep_mock = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep_mock)

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))

    assert out == {"status_code": 400, "error": "bad", "message_id": ""}
    assert len(fake.calls) == 1
    sleep_mock.assert_not_called()


def test_send_email_429_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """429 triggers retry and a subsequent 202 returns success."""
    fake = _FakeAsyncClient([
        _mk_response(429),
        _mk_response(202, headers={"X-Message-Id": "ok"}),
    ])
    _patch_client(monkeypatch, fake)
    sleep_mock = AsyncMock()
    monkeypatch.setattr("asyncio.sleep", sleep_mock)

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))

    assert out["status_code"] == 202
    assert out["message_id"] == "ok"
    assert len(fake.calls) == 2
    sleep_mock.assert_awaited_once()


def test_send_email_5xx_retries_then_max_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All MAX_RETRIES return 503 -> falls through to max-retries result."""
    fake = _FakeAsyncClient([_mk_response(503) for _ in range(MAX_RETRIES)])
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))

    assert out == {"status_code": 0, "error": "Max retries exceeded", "message_id": ""}
    assert len(fake.calls) == MAX_RETRIES


def test_send_email_http_error_retries_then_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All retries raise httpx.HTTPError -> last exception is re-raised."""
    err = httpx.ConnectError("boom")
    fake = _FakeAsyncClient([err for _ in range(MAX_RETRIES)])
    _patch_client(monkeypatch, fake)
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    with pytest.raises(httpx.HTTPError):
        _run(a.send_email(to="t@e.io", subject="s", body_html="h", body_text="t"))
    assert len(fake.calls) == MAX_RETRIES


def test_send_sms_not_supported() -> None:
    """SendGrid does not support SMS."""
    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    with pytest.raises(NotImplementedError):
        _run(a.send_sms(to="+1", message="x"))


def test_make_call_not_supported() -> None:
    """SendGrid does not support voice calls."""
    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    with pytest.raises(NotImplementedError):
        _run(a.make_call(to="+1", script="x"))


def test_normalize_webhook_event_full_payload() -> None:
    """Normalizes all known fields and strips suffix from sg_message_id."""
    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.normalize_webhook_event({
        "event": "delivered",
        "sg_event_id": "ev-1",
        "email": "x@e.io",
        "timestamp": 123,
        "sg_message_id": "abc.filter0001p3las1-12345",
    }))
    assert out == {
        "event_type": "delivered",
        "provider_event_id": "ev-1",
        "contact_identifier": "x@e.io",
        "occurred_at": 123,
        "provider_message_id": "abc",
    }


def test_normalize_webhook_event_defaults_for_missing_fields() -> None:
    """Defaults apply when fields are missing."""
    a = SendGridAdapter(api_key="k", from_email="f@e.io")
    out = _run(a.normalize_webhook_event({}))
    assert out["event_type"] == "unknown"
    assert out["provider_event_id"] == ""
    assert out["contact_identifier"] == ""
    assert out["occurred_at"] == ""
    assert out["provider_message_id"] == ""


def test_verify_webhook_signature_no_secret_returns_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without configured secret, verification fails closed."""
    monkeypatch.setattr(settings, "SENDGRID_WEBHOOK_SECRET", "")
    assert SendGridAdapter.verify_webhook_signature(b"body", "sig", "ts") is False


def test_verify_webhook_signature_valid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Correct HMAC-SHA256 signature passes verification."""
    monkeypatch.setattr(settings, "SENDGRID_WEBHOOK_SECRET", "shh")
    payload = b"body"
    timestamp = "1700000000"
    signed = timestamp.encode() + payload
    expected = hmac.new(b"shh", signed, hashlib.sha256).hexdigest()
    assert SendGridAdapter.verify_webhook_signature(payload, expected, timestamp) is True


def test_verify_webhook_signature_invalid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wrong signature is rejected."""
    monkeypatch.setattr(settings, "SENDGRID_WEBHOOK_SECRET", "shh")
    assert SendGridAdapter.verify_webhook_signature(b"body", "deadbeef", "ts") is False
