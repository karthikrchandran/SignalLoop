from __future__ import annotations

import asyncio
import base64
import json

from app.api.routes.voice import (
    _cancel_task,
    _stream_text_to_twilio,
    _token_hash,
)


def test_media_stream_nonce_is_stored_as_a_hash() -> None:
    assert _token_hash("opaque-token") != "opaque-token"
    assert _token_hash("opaque-token") != _token_hash("different-token")


def test_cancel_task_awaits_cancellation_cleanup() -> None:
    async def run() -> None:
        cleaned = False

        async def sleeper() -> None:
            nonlocal cleaned
            try:
                await asyncio.sleep(60)
            finally:
                cleaned = True

        task = asyncio.create_task(sleeper())
        await asyncio.sleep(0)
        await _cancel_task(task)

        assert cleaned is True
        assert task.cancelled() is True

    asyncio.run(run())


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, message: str) -> None:
        self.sent.append(json.loads(message))


class FakeEngine:
    async def synthesize_response_stream(self, text: str):
        yield b"abc"
        yield b"def"


def test_stream_text_to_twilio_sends_audio_chunks_as_they_arrive() -> None:
    async def run() -> FakeWebSocket:
        websocket = FakeWebSocket()
        sent_first_audio = await _stream_text_to_twilio(
            websocket,
            "MZ123",
            FakeEngine(),
            "hello",
        )
        assert sent_first_audio is True
        return websocket

    websocket = asyncio.run(run())

    assert [message["event"] for message in websocket.sent] == ["media", "media"]
    assert [message["streamSid"] for message in websocket.sent] == ["MZ123", "MZ123"]
    assert base64.b64decode(websocket.sent[0]["media"]["payload"]) == b"abc"
    assert base64.b64decode(websocket.sent[1]["media"]["payload"]) == b"def"
