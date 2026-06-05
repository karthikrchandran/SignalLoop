"""Deepgram Aura streaming TTS adapter."""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.infrastructure.providers.base import TtsAdapter
from app.infrastructure.providers.errors import require_provider_key

logger = logging.getLogger(__name__)

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"
DEEPGRAM_TTS_TIMEOUT = httpx.Timeout(2.0, connect=0.5, read=1.5, write=0.5, pool=0.5)


class DeepgramTTSAdapter(TtsAdapter):
    """Text-to-speech via Deepgram Aura API, returns μ-law audio."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = require_provider_key(api_key or settings.DEEPGRAM_API_KEY, "DEEPGRAM_API_KEY")

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to μ-law 8kHz audio bytes."""
        params = {
            "model": "aura-asteria-en",
            "encoding": "mulaw",
            "sample_rate": "8000",
        }
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }
        if not text.strip():
            return b""
        try:
            async with httpx.AsyncClient(timeout=DEEPGRAM_TTS_TIMEOUT) as client:
                resp = await client.post(
                    DEEPGRAM_TTS_URL,
                    params=params,
                    headers=headers,
                    json={"text": text},
                )
                if resp.status_code == 200:
                    return resp.content
                logger.error("Deepgram TTS error: status=%d", resp.status_code)
        except httpx.HTTPError:
            logger.exception("Deepgram TTS request failed")
        return b""

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream TTS audio chunks for lower latency."""
        params = {
            "model": "aura-asteria-en",
            "encoding": "mulaw",
            "sample_rate": "8000",
        }
        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
        }
        if not text.strip():
            return
        try:
            async with httpx.AsyncClient(timeout=DEEPGRAM_TTS_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    DEEPGRAM_TTS_URL,
                    params=params,
                    headers=headers,
                    json={"text": text},
                ) as resp:
                    if resp.status_code != 200:
                        logger.error("Deepgram TTS stream error: status=%d", resp.status_code)
                        return
                    async for chunk in resp.aiter_bytes(chunk_size=640):
                        if chunk:
                            yield chunk
        except httpx.HTTPError:
            logger.exception("Deepgram TTS stream request failed")
