"""Unit tests for ``app.infrastructure.providers.openai_llm``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.infrastructure.providers import openai_llm as openai_mod
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.openai_llm import OpenAILLMAdapter


def _run(coro):
    return asyncio.run(coro)


class _Client:
    def __init__(self, response_or_exc: Any) -> None:
        self._r = response_or_exc
        self.calls: list[dict[str, Any]] = []

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
    monkeypatch.setattr(openai_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_init_requires_api_key() -> None:
    with pytest.raises(ProviderConfigurationError):
        OpenAILLMAdapter(api_key="")


def test_chat_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    client = _Client(resp)
    _patch(monkeypatch, client)

    a = OpenAILLMAdapter(api_key="sk-x")
    out = _run(a.chat_completion(system_prompt="s", messages=[{"role": "user", "content": "hi"}]))
    assert out == "ok"
    call = client.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-x"
    assert call["json"]["model"] == "gpt-4o-mini"
    assert call["json"]["messages"][0]["role"] == "system"


def test_chat_completion_custom_base_url_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenRouter/Together pathways: base_url + model override."""
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": [{"message": {"content": "yes"}}]}
    client = _Client(resp)
    _patch(monkeypatch, client)

    a = OpenAILLMAdapter(
        api_key="or-x",
        base_url="https://openrouter.ai/api/v1/",
        model="meta-llama/llama-3.1-8b-instruct",
    )
    out = _run(a.chat_completion(system_prompt="s", messages=[{"role": "user", "content": "hi"}]))
    assert out == "yes"
    call = client.calls[0]
    # Trailing slash stripped:
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert call["json"]["model"] == "meta-llama/llama-3.1-8b-instruct"


def test_chat_completion_empty_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"choices": []}
    _patch(monkeypatch, _Client(resp))
    a = OpenAILLMAdapter(api_key="k")
    assert _run(a.chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.side_effect = ValueError("bad")
    _patch(monkeypatch, _Client(resp))
    a = OpenAILLMAdapter(api_key="k")
    assert _run(a.chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=500)
    _patch(monkeypatch, _Client(resp))
    a = OpenAILLMAdapter(api_key="k")
    assert _run(a.chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _Client(httpx.ConnectError("nope")))
    a = OpenAILLMAdapter(api_key="k")
    assert _run(a.chat_completion(system_prompt="s", messages=[])) == ""
