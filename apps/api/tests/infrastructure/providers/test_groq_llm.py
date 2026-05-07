"""Unit tests for ``app.infrastructure.providers.groq_llm``.

Covers fail-fast, payload construction, success extraction, empty-choices
fallback, invalid JSON, non-200 status logging, and HTTPError handling.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import settings
from app.infrastructure.providers import groq_llm as groq_mod
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.groq_llm import GROQ_API_URL, GroqLLMAdapter


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GROQ_API_KEY", "gk")


class _Client:
    """Async context manager replacement for ``httpx.AsyncClient``."""

    def __init__(self, response_or_exc: Any) -> None:
        self._r = response_or_exc
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *a, **k):  # pragma: no cover
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, headers=None, json=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "json": json})
        if isinstance(self._r, Exception):
            raise self._r
        return self._r


def _patch(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    monkeypatch.setattr(groq_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction raises when GROQ_API_KEY is empty."""
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    with pytest.raises(ProviderConfigurationError):
        GroqLLMAdapter()


def test_chat_completion_returns_assistant_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 with at least one choice returns the message content."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}]
    }
    client = _Client(resp)
    _patch(monkeypatch, client)

    a = GroqLLMAdapter()
    out = _run(a.chat_completion(
        system_prompt="sys",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=42,
        temperature=0.1,
    ))
    assert out == "hello world"
    call = client.calls[0]
    assert call["url"] == GROQ_API_URL
    assert call["headers"]["Authorization"] == "Bearer gk"
    payload = call["json"]
    assert payload["model"] == "llama-3.1-8b-instant"
    assert payload["max_tokens"] == 42
    assert payload["temperature"] == 0.1
    assert payload["messages"][0] == {"role": "system", "content": "sys"}
    assert payload["messages"][1] == {"role": "user", "content": "hi"}


def test_chat_completion_empty_choices_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 with no choices yields the empty string."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": []}
    _patch(monkeypatch, _Client(resp))
    assert _run(GroqLLMAdapter().chat_completion(
        system_prompt="s", messages=[]
    )) == ""


def test_chat_completion_missing_message_content_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A choice without message.content falls back to empty string."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{}]}
    _patch(monkeypatch, _Client(resp))
    assert _run(GroqLLMAdapter().chat_completion(
        system_prompt="s", messages=[]
    )) == ""


def test_chat_completion_invalid_json_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 with invalid JSON body returns empty and logs."""
    resp = MagicMock(status_code=200)
    resp.json.side_effect = ValueError("bad json")
    _patch(monkeypatch, _Client(resp))
    assert _run(GroqLLMAdapter().chat_completion(
        system_prompt="s", messages=[]
    )) == ""


def test_chat_completion_non_200_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-200 status returns empty string."""
    resp = MagicMock(status_code=500)
    _patch(monkeypatch, _Client(resp))
    assert _run(GroqLLMAdapter().chat_completion(
        system_prompt="s", messages=[]
    )) == ""


def test_chat_completion_http_error_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTPError is caught and empty string returned."""
    _patch(monkeypatch, _Client(httpx.ConnectError("boom")))
    assert _run(GroqLLMAdapter().chat_completion(
        system_prompt="s", messages=[]
    )) == ""
