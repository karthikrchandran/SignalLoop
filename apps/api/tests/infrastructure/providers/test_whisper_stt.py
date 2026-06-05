"""Unit tests for ``app.infrastructure.providers.whisper_stt``."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest

from app.infrastructure.providers import whisper_stt as whisper_mod
from app.infrastructure.providers.errors import ProviderConfigurationError
from app.infrastructure.providers.whisper_stt import FasterWhisperLocalAdapter


def _run(coro):
    return asyncio.run(coro)


class _Client:
    def __init__(self, response_or_exc: Any) -> None:
        self._response_or_exc = response_or_exc
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def post(self, url, files=None, data=None, **kwargs):
        self.calls.append({"url": url, "files": files, "data": data})
        if isinstance(self._response_or_exc, Exception):
            raise self._response_or_exc
        return self._response_or_exc


def _patch(monkeypatch: pytest.MonkeyPatch, client: _Client) -> None:
    monkeypatch.setattr(whisper_mod.httpx, "AsyncClient", lambda *a, **k: client)


async def _collect(gen):
    out = []
    async for item in gen:
        out.append(item)
    return out


def test_init_requires_base_url() -> None:
    with pytest.raises(ProviderConfigurationError):
        FasterWhisperLocalAdapter(base_url="")


def test_connect_then_close_with_no_audio_sets_closed() -> None:
    adapter = FasterWhisperLocalAdapter()

    _run(adapter.connect())
    _run(adapter.close())

    assert adapter._final_transcript == ""
    assert adapter._closed is True


def test_close_posts_buffered_audio_once(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "text": "hello world",
        "language": "en",
        "duration": 1.0,
    }
    client = _Client(resp)
    _patch(monkeypatch, client)

    adapter = FasterWhisperLocalAdapter(
        base_url="http://stt:9000/",
        model="small",
    )
    _run(adapter.connect())
    _run(adapter.send_audio(b"fake"))
    _run(adapter.send_audio(b"fake"))
    _run(adapter.send_audio(b"fake"))
    _run(adapter.close())

    assert adapter._final_transcript == "hello world"
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "http://stt:9000/transcribe"
    assert call["data"] == {"model": "small"}


def test_close_logs_http_error_and_sets_closed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _patch(monkeypatch, _Client(httpx.ConnectError("down")))
    adapter = FasterWhisperLocalAdapter()

    _run(adapter.connect())
    _run(adapter.send_audio(b"fake"))
    _run(adapter.close())

    assert adapter._closed is True
    assert "FasterWhisper HTTP request failed" in caplog.text


def test_close_handles_invalid_json_and_sets_closed(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    resp = MagicMock(status_code=200)
    resp.json.side_effect = ValueError("bad")
    _patch(monkeypatch, _Client(resp))
    adapter = FasterWhisperLocalAdapter()

    _run(adapter.connect())
    _run(adapter.send_audio(b"fake"))
    _run(adapter.close())

    assert adapter._closed is True
    assert adapter._final_transcript == ""
    assert "FasterWhisper service returned invalid JSON" in caplog.text


def test_receive_loop_yields_final_event(monkeypatch: pytest.MonkeyPatch) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {
        "text": "hello world",
        "language": "en",
        "duration": 1.0,
    }
    _patch(monkeypatch, _Client(resp))

    adapter = FasterWhisperLocalAdapter()
    _run(adapter.connect())
    _run(adapter.send_audio(b"fake"))
    _run(adapter.close())

    events = _run(_collect(adapter.receive_loop()))

    assert events == [
        {
            "type": "transcript",
            "is_final": True,
            "text": "hello world",
        }
    ]
