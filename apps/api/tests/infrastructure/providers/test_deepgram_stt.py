"""Unit tests for ``app.infrastructure.providers.deepgram_stt``.

Covers fail-fast on missing key, WebSocket connect parameters, send_audio
behavior, JSON parsing in receive loop (valid/malformed/no-transcript),
on_transcript callback dispatch, ``ConnectionClosed`` handling, generic
exception handling, and the close timeout fallback.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import websockets

from app.core.config import settings
from app.infrastructure.providers import deepgram_stt as stt_mod
from app.infrastructure.providers.deepgram_stt import (
    DEEPGRAM_WS_URL,
    DeepgramSTTAdapter,
)
from app.infrastructure.providers.errors import ProviderConfigurationError


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-key")


def test_init_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Construction raises when API key is empty."""
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "")
    with pytest.raises(ProviderConfigurationError):
        DeepgramSTTAdapter()


def test_connect_passes_url_and_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """connect() builds the right URL and Authorization header."""
    fake_ws = MagicMock()
    connect_mock = AsyncMock(return_value=fake_ws)
    monkeypatch.setattr(stt_mod.websockets, "connect", connect_mock)

    a = DeepgramSTTAdapter()
    _run(a.connect())

    args, kwargs = connect_mock.call_args
    assert args[0].startswith(DEEPGRAM_WS_URL + "?")
    assert "model=nova-2" in args[0]
    assert "encoding=mulaw" in args[0]
    assert kwargs["additional_headers"]["Authorization"] == "Token dg-key"
    assert a._ws is fake_ws


def test_send_audio_no_op_when_not_connected() -> None:
    """send_audio is a no-op when the socket is not open."""
    a = DeepgramSTTAdapter()
    _run(a.send_audio(b"abc"))  # should not raise


def test_send_audio_forwards_bytes_to_socket() -> None:
    """send_audio forwards bytes to the underlying websocket."""
    a = DeepgramSTTAdapter()
    a._ws = MagicMock()
    a._ws.send = AsyncMock()
    _run(a.send_audio(b"abc"))
    a._ws.send.assert_awaited_once_with(b"abc")


class _AsyncIter:
    """Async iterator yielding the supplied messages or raising at end."""

    def __init__(self, messages: list[Any], raise_at_end: Exception | None = None) -> None:
        self._messages = list(messages)
        self._raise = raise_at_end

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        if self._raise is not None:
            raise self._raise
        raise StopAsyncIteration


async def _collect(gen):
    out = []
    async for item in gen:
        out.append(item)
    return out


def test_receive_loop_no_socket_returns_immediately() -> None:
    """receive_loop short-circuits when no socket is set."""
    a = DeepgramSTTAdapter()
    out = _run(_collect(a.receive_loop()))
    assert out == []


def test_receive_loop_yields_transcripts_and_invokes_callback() -> None:
    """Valid messages with transcripts are yielded and callback fires."""
    cb = MagicMock()
    a = DeepgramSTTAdapter(on_transcript=cb)
    msg = json.dumps({
        "channel": {"alternatives": [{"transcript": "hello"}]},
        "is_final": True,
    })
    a._ws = _AsyncIter([msg])

    out = _run(_collect(a.receive_loop()))
    assert out == [{"transcript": "hello", "is_final": True}]
    cb.assert_called_once_with("hello", True)


def test_receive_loop_skips_empty_transcript_and_malformed_json() -> None:
    """Malformed JSON is skipped; empty transcripts are not yielded."""
    a = DeepgramSTTAdapter()
    msgs = [
        "not-json",
        json.dumps({"channel": {"alternatives": [{"transcript": ""}]}}),
        json.dumps({"channel": {"alternatives": [{"transcript": "ok"}], }, "is_final": False}),
    ]
    a._ws = _AsyncIter(msgs)
    out = _run(_collect(a.receive_loop()))
    assert out == [{"transcript": "ok", "is_final": False}]


def test_receive_loop_swallows_connection_closed() -> None:
    """ConnectionClosed during iteration ends the generator cleanly."""
    a = DeepgramSTTAdapter()
    a._ws = _AsyncIter(
        [],
        raise_at_end=websockets.exceptions.ConnectionClosed(None, None),
    )
    out = _run(_collect(a.receive_loop()))
    assert out == []


def test_receive_loop_swallows_unexpected_exception() -> None:
    """Generic exceptions during iteration are logged and suppressed."""
    a = DeepgramSTTAdapter()
    a._ws = _AsyncIter([], raise_at_end=RuntimeError("kaboom"))
    out = _run(_collect(a.receive_loop()))
    assert out == []


def test_close_no_op_when_no_socket() -> None:
    """close() is safe when no socket exists."""
    a = DeepgramSTTAdapter()
    _run(a.close())  # no exception


def test_close_calls_socket_close() -> None:
    """close() awaits the underlying socket close and clears the ref."""
    a = DeepgramSTTAdapter()
    ws = MagicMock()
    ws.close = AsyncMock()
    a._ws = ws
    _run(a.close())
    ws.close.assert_awaited()
    assert a._ws is None


def test_close_swallows_timeout() -> None:
    """A timeout during close is suppressed."""
    a = DeepgramSTTAdapter()
    ws = MagicMock()
    ws.close = AsyncMock(side_effect=asyncio.TimeoutError())
    a._ws = ws
    _run(a.close())  # no exception
    assert a._ws is None
