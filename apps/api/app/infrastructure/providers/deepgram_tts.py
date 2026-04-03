"""Deepgram Aura streaming TTS adapter."""
from __future__ import annotations

import logging
from typing import AsyncGenerator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak"


class DeepgramTTSAdapter:
    """Text-to-speech via Deepgram Aura API, returns μ-law audio."""

    def __init__(self) -> None:
        self._api_key = settings.DEEPGRAM_API_KEY

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
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPGRAM_TTS_URL,
                params=params,
                headers=headers,
                json={"text": text},
            )
            if resp.status_code == 200:
                return resp.content
            logger.error("Deepgram TTS error: %d %s", resp.status_code, resp.text)
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                DEEPGRAM_TTS_URL,
                params=params,
                headers=headers,
                json={"text": text},
            ) as resp:
                if resp.status_code != 200:
                    logger.error("Deepgram TTS stream error: %d", resp.status_code)
                    return
                async for chunk in resp.aiter_bytes(chunk_size=640):
                    yield chunk
