"""Unit tests for ``app.infrastructure.providers.smtp_email``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import aiosmtplib
import pytest

from app.infrastructure.providers import smtp_email as smtp_mod
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.smtp_email import SmtpEmailAdapter


def _run(coro):
    return asyncio.run(coro)


def test_init_requires_host() -> None:
    with pytest.raises(ProviderConfigurationError):
        SmtpEmailAdapter(host="", from_email="a@b.io")


def test_init_requires_from_email() -> None:
    with pytest.raises(ProviderConfigurationError):
        SmtpEmailAdapter(host="smtp.example.com", from_email="")


def test_implicit_tls_disables_starttls() -> None:
    a = SmtpEmailAdapter(
        host="smtp.example.com",
        from_email="a@b.io",
        use_tls=True,
        use_starttls=True,
    )
    assert a._use_tls is True
    assert a._use_starttls is False


def test_send_email_success_returns_250(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful aiosmtplib.send returns 250 with the Message-Id."""
    captured: dict[str, Any] = {}

    async def fake_send(msg, **kwargs):
        captured["msg"] = msg
        captured["kwargs"] = kwargs
        msg["Message-Id"] = "<id@host>"
        return ({}, "ok")

    monkeypatch.setattr(smtp_mod.aiosmtplib, "send", fake_send)

    a = SmtpEmailAdapter(
        host="smtp.example.com",
        port=2525,
        username="u",
        password="p",
        from_email="from@example.com",
        from_name="Ops",
    )
    out = _run(a.send_email(
        to="to@example.com",
        subject="Hi",
        body_html="<p>Hi</p>",
        body_text="Hi",
        reply_to="reply@example.com",
        idempotency_key="abc",
    ))

    assert out["status_code"] == 250
    assert out["message_id"] == "<id@host>"
    msg = captured["msg"]
    assert msg["To"] == "to@example.com"
    assert msg["From"] == "Ops <from@example.com>"
    assert msg["Reply-To"] == "reply@example.com"
    assert msg["X-Idempotency-Key"] == "abc"
    assert msg.is_multipart() is True
    assert captured["kwargs"]["hostname"] == "smtp.example.com"
    assert captured["kwargs"]["port"] == 2525
    assert captured["kwargs"]["start_tls"] is True


def test_send_email_handles_smtp_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_send(msg, **kwargs):
        raise aiosmtplib.SMTPException("boom")

    monkeypatch.setattr(smtp_mod.aiosmtplib, "send", fake_send)
    a = SmtpEmailAdapter(host="h", from_email="f@x.io")
    out = _run(a.send_email(to="t@x.io", subject="s", body_html="<p/>", body_text="t"))
    assert out["status_code"] == 0
    assert out["error"] == "smtp_send_failed"


def test_send_email_handles_rejected_recipients(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_send(msg, **kwargs):
        return ({"t@x.io": (550, b"no")}, "ok")

    monkeypatch.setattr(smtp_mod.aiosmtplib, "send", fake_send)
    a = SmtpEmailAdapter(host="h", from_email="f@x.io")
    out = _run(a.send_email(to="t@x.io", subject="s", body_html="<p/>", body_text="t"))
    assert out["status_code"] == 550
    assert out["error"] == "smtp_recipients_rejected"
