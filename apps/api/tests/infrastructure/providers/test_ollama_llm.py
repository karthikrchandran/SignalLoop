"""Unit tests for ``app.infrastructure.providers.ollama_llm``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.infrastructure.providers import ollama_llm as ollama_mod
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.ollama_llm import OllamaLLMAdapter


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

    async def post(self, url, json=None, **kwargs):
        self.calls.append({"url": url, "json": json})
        if isinstance(self._r, Exception):
            raise self._r
        return self._r


def _patch(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    monkeypatch.setattr(ollama_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_default_base_url_and_model() -> None:
    a = OllamaLLMAdapter()
    assert a._base_url == "http://localhost:11434"
    assert a._model == "llama3.2:1b"


def test_init_requires_base_url() -> None:
    with pytest.raises(ProviderConfigurationError):
        OllamaLLMAdapter(base_url="")


def test_chat_completion_success(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"message": {"content": "hi back"}}
    client = _Client(resp)
    _patch(monkeypatch, client)

    a = OllamaLLMAdapter(base_url="http://ollama:11434/", model="qwen2:7b")
    out = _run(a.chat_completion(
        system_prompt="s",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=99,
        temperature=0.2,
    ))
    assert out == "hi back"
    call = client.calls[0]
    assert call["url"] == "http://ollama:11434/api/chat"
    assert call["json"]["model"] == "qwen2:7b"
    assert call["json"]["stream"] is False
    assert call["json"]["options"]["num_predict"] == 99
    assert call["json"]["options"]["temperature"] == 0.2
    assert call["json"]["messages"][0] == {"role": "system", "content": "s"}


def test_chat_completion_missing_message(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {}
    _patch(monkeypatch, _Client(resp))
    assert _run(OllamaLLMAdapter().chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.side_effect = ValueError("bad")
    _patch(monkeypatch, _Client(resp))
    assert _run(OllamaLLMAdapter().chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _Client(MagicMock(status_code=503)))
    assert _run(OllamaLLMAdapter().chat_completion(system_prompt="s", messages=[])) == ""


def test_chat_completion_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, _Client(httpx.ConnectError("down")))
    assert _run(OllamaLLMAdapter().chat_completion(system_prompt="s", messages=[])) == ""
