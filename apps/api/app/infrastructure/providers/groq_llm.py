"""Groq LLM adapter using Llama 3.1 8B for voice AI responses."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.infrastructure.providers.base import LlmAdapter
from app.infrastructure.providers.errors import require_provider_key

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = httpx.Timeout(0.8, connect=0.25, read=0.6, write=0.25, pool=0.25)


class GroqLLMAdapter(LlmAdapter):
    """Chat completion via Groq API (Llama 3.1 8B Instant)."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = require_provider_key(api_key or settings.GROQ_API_KEY, "GROQ_API_KEY")

    async def chat_completion(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 80,
        temperature: float = 0.4,
        **kwargs: Any,
    ) -> str:
        """Send messages to Groq and return the assistant response text."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=GROQ_TIMEOUT) as client:
                resp = await client.post(GROQ_API_URL, headers=headers, json=payload)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        logger.error("Groq LLM returned invalid JSON")
                        return ""
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                logger.error("Groq LLM error: status=%d", resp.status_code)
        except httpx.HTTPError:
            logger.exception("Groq LLM request failed")
        return ""
