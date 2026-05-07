"""Unit tests for ``app.infrastructure.providers.deepgram_tts``.

Covers fail-fast, empty-text short-circuit, success body return, error
status logging, HTTPError swallowing, and the streaming variant
(success, error status, exception, empty text).
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.core.config import settings
from app.infrastructure.providers import deepgram_tts as tts_mod
from app.infrastructure.providers.deepgram_tts import DeepgramTTSAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-key")


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty key raises ProviderConfigurationError at construction."""
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "")
    with pytest.raises(ProviderConfigurationError):
        DeepgramTTSAdapter()


# ---------------- synthesize() ----------------

class _PostClient:
    """Replacement for ``httpx.AsyncClient`` for non-streaming POST."""

    def __init__(self, response_or_exc: Any) -> None:
        self._r = response_or_exc
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *a, **k):  # pragma: no cover
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, params=None, headers=None, json=None, **kwargs):
        self.calls.append({"url": url, "params": params, "headers": headers, "json": json})
        if isinstance(self._r, Exception):
            raise self._r
        return self._r


def _patch_client(monkeypatch: pytest.MonkeyPatch, client: Any) -> None:
    monkeypatch.setattr(tts_mod.httpx, "AsyncClient", lambda *a, **k: client)


def test_synthesize_returns_empty_for_blank_text() -> None:
    """Blank/whitespace text returns ``b''`` without an HTTP call."""
    a = DeepgramTTSAdapter()
    assert _run(a.synthesize("   ")) == b""


def test_synthesize_returns_audio_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 response returns the response body as bytes."""
    resp = MagicMock(status_code=200, content=b"\x01\x02")
    client = _PostClient(resp)
    _patch_client(monkeypatch, client)
    a = DeepgramTTSAdapter()
    assert _run(a.synthesize("hi")) == b"\x01\x02"
    call = client.calls[0]
    assert call["headers"]["Authorization"] == "Token dg-key"
    assert call["json"] == {"text": "hi"}
    assert call["params"]["encoding"] == "mulaw"


def test_synthesize_returns_empty_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-200 status returns empty bytes and is logged."""
    resp = MagicMock(status_code=500, content=b"err")
    _patch_client(monkeypatch, _PostClient(resp))
    a = DeepgramTTSAdapter()
    assert _run(a.synthesize("hi")) == b""


def test_synthesize_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPError is caught and empty bytes returned."""
    _patch_client(monkeypatch, _PostClient(httpx.ConnectError("boom")))
    a = DeepgramTTSAdapter()
    assert _run(a.synthesize("hi")) == b""


# ---------------- synthesize_stream() ----------------

class _StreamCM:
    """Async context manager replacement for client.stream(...) result."""

    def __init__(self, status_code: int, chunks: list[bytes]) -> None:
        self.status_code = status_code
        self._chunks = chunks

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def aiter_bytes(self, chunk_size: int = 0):
        for c in self._chunks:
            yield c


class _StreamClient:
    """Replacement for ``httpx.AsyncClient`` exposing ``stream()``."""

    def __init__(self, stream_cm_or_exc: Any) -> None:
        self._s = stream_cm_or_exc

    def __call__(self, *a, **k):  # pragma: no cover
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    def stream(self, method, url, params=None, headers=None, json=None, **kwargs):
        if isinstance(self._s, Exception):
            raise self._s
        return self._s


async def _collect(gen):
    out = []
    async for c in gen:
        out.append(c)
    return out


def test_synthesize_stream_blank_text_yields_nothing() -> None:
    """Blank text yields no chunks."""
    a = DeepgramTTSAdapter()
    assert _run(_collect(a.synthesize_stream("   "))) == []


def test_synthesize_stream_yields_chunks_on_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """200 stream yields each non-empty chunk; empty chunks are filtered."""
    cm = _StreamCM(200, [b"abc", b"", b"def"])
    monkeypatch.setattr(tts_mod.httpx, "AsyncClient", lambda *a, **k: _StreamClient(cm))
    a = DeepgramTTSAdapter()
    assert _run(_collect(a.synthesize_stream("hi"))) == [b"abc", b"def"]


def test_synthesize_stream_returns_on_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-200 stream returns without yielding chunks."""
    cm = _StreamCM(500, [b"x"])
    monkeypatch.setattr(tts_mod.httpx, "AsyncClient", lambda *a, **k: _StreamClient(cm))
    a = DeepgramTTSAdapter()
    assert _run(_collect(a.synthesize_stream("hi"))) == []


def test_synthesize_stream_swallows_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """HTTPError raised by stream() is caught and the generator ends."""
    monkeypatch.setattr(
        tts_mod.httpx, "AsyncClient",
        lambda *a, **k: _StreamClient(httpx.ConnectError("boom")),
    )
    a = DeepgramTTSAdapter()
    assert _run(_collect(a.synthesize_stream("hi"))) == []
