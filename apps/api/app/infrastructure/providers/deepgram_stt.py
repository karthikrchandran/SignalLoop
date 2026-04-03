"""Deepgram Nova-2 streaming STT adapter."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Callable

import websockets

from app.core.config import settings

logger = logging.getLogger(__name__)

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramSTTAdapter:
    """Streaming speech-to-text via Deepgram Nova-2 WebSocket API."""

    def __init__(
        self,
        *,
        on_transcript: Callable[[str, bool], Any] | None = None,
    ) -> None:
        self._api_key = settings.DEEPGRAM_API_KEY
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
            "&endpointing=300"
        )
        headers = {"Authorization": f"Token {self._api_key}"}
        self._ws = await websockets.connect(
            f"{DEEPGRAM_WS_URL}{params}",
            additional_headers=headers,
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
                data = json.loads(message)
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

    async def close(self) -> None:
        """Close the STT WebSocket."""
        if self._ws:
            await self._ws.close()
            self._ws = None
