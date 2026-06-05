"""Local faster-whisper STT adapter."""
from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.infrastructure.providers.base import SttAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:9000"
_DEFAULT_MODEL = "base"
_WHISPER_TIMEOUT = httpx.Timeout(120.0, connect=5.0)


class FasterWhisperLocalAdapter(SttAdapter):
    """STT via a local faster-whisper HTTP microservice.

    Audio is buffered during the session and transcribed in one batch call
    when close() is called. Use this for post-call transcription rather than
    realtime voice streaming.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        url = (base_url if base_url is not None else _DEFAULT_BASE_URL).rstrip("/")
        if not url:
            raise ProviderConfigurationError(
                "faster_whisper base_url is not configured"
            )
        self._base_url = url
        self._model = model or _DEFAULT_MODEL
        self._buffer: list[bytes] = []
        self._final_transcript = ""
        self._closed = False

    async def connect(self) -> None:
        """Reset the in-memory audio buffer."""
        self._buffer = []
        self._final_transcript = ""
        self._closed = False

    async def send_audio(self, audio_bytes: bytes) -> None:
        """Buffer incoming audio for batch transcription."""
        if not self._closed:
            self._buffer.append(audio_bytes)

    async def receive_loop(self) -> AsyncGenerator[dict[str, Any], None]:
        """Yield one final transcript event after close() completes."""
        for _ in range(120):
            if self._closed:
                break
            await asyncio.sleep(0.5)

        if self._final_transcript:
            yield {
                "type": "transcript",
                "is_final": True,
                "text": self._final_transcript,
            }

    async def close(self) -> None:
        """Flush buffered audio to the local STT service."""
        if not self._buffer:
            self._closed = True
            return

        audio_blob = b"".join(self._buffer)
        self._buffer = []

        try:
            async with httpx.AsyncClient(timeout=_WHISPER_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/transcribe",
                    files={
                        "audio": (
                            "audio.raw",
                            io.BytesIO(audio_blob),
                            "application/octet-stream",
                        )
                    },
                    data={"model": self._model},
                )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        logger.error("FasterWhisper service returned invalid JSON")
                        return
                    self._final_transcript = data.get("text", "").strip()
                    logger.info(
                        "FasterWhisper transcribed %d bytes to %d chars",
                        len(audio_blob),
                        len(self._final_transcript),
                    )
                else:
                    logger.error(
                        "FasterWhisper service error: status=%d body=%s",
                        resp.status_code,
                        resp.text[:200],
                    )
        except httpx.HTTPError:
            logger.exception("FasterWhisper HTTP request failed")
        finally:
            self._closed = True
