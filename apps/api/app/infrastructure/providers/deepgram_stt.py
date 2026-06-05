"""Deepgram Nova-2 streaming STT adapter."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Callable

import websockets

from app.core.config import settings
from app.infrastructure.providers.base import SttAdapter
from app.infrastructure.providers.errors import require_provider_key

logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"
STT_CONNECT_TIMEOUT_SECONDS = 2.0
STT_CLOSE_TIMEOUT_SECONDS = 1.0
STT_ENDPOINTING_MS = 80


class DeepgramSTTAdapter(SttAdapter):
    """Streaming speech-to-text via Deepgram Nova-2 WebSocket API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        on_transcript: Callable[[str, bool], Any] | None = None,
    ) -> None:
        self._api_key = require_provider_key(api_key or settings.DEEPGRAM_API_KEY, "DEEPGRAM_API_KEY")
        self._ws = None
        self._on_transcript = on_transcript

    async def connect(self) -> None:
        """Open streaming WebSocket to Deepgram."""
        params = (
            "?model=nova-2"
            "&language=en"
            "&encoding=mulaw"
            "&sample_rate=8000"
            "&channels=1"
            "&interim_results=true"
            "&punctuate=true"
            f"&endpointing={STT_ENDPOINTING_MS}"
        )
        headers = {"Authorization": f"Token {self._api_key}"}
        self._ws = await websockets.connect(
            f"{DEEPGRAM_WS_URL}{params}",
            additional_headers=headers,
            open_timeout=STT_CONNECT_TIMEOUT_SECONDS,
            close_timeout=STT_CLOSE_TIMEOUT_SECONDS,
        )
        logger.info("Deepgram STT connected")

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Send raw audio chunk to Deepgram."""
        if self._ws:
            await self._ws.send(audio_bytes)

    async def receive_loop(self) -> AsyncGenerator[dict[str, Any], None]:
        """Listen for transcription results from Deepgram."""
        if not self._ws:
            return
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning("Deepgram STT returned malformed JSON")
                    continue
                channel = data.get("channel", {})
                alternatives = channel.get("alternatives", [{}])
                if alternatives:
                    transcript = alternatives[0].get("transcript", "")
                    is_final = data.get("is_final", False)
                    if transcript:
                        if self._on_transcript:
                            self._on_transcript(transcript, is_final)
                        yield {"transcript": transcript, "is_final": is_final}
        except websockets.exceptions.ConnectionClosed:
            logger.info("Deepgram STT connection closed")
        except Exception:
            logger.exception("Deepgram STT receive loop failed")

    async def close(self) -> None:
        """Close the STT WebSocket."""
        if self._ws:
            ws = self._ws
            self._ws = None
            try:
                await asyncio.wait_for(ws.close(), timeout=STT_CLOSE_TIMEOUT_SECONDS)
            except (asyncio.TimeoutError, websockets.exceptions.WebSocketException):
                logger.warning("Deepgram STT close did not complete cleanly")
