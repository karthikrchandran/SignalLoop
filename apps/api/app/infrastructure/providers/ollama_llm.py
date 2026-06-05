"""Ollama LLM adapter — drives a self-hosted Ollama server.

Operators install Ollama locally (https://ollama.com) and point this adapter
at the server's base URL (default ``http://localhost:11434``).  We talk to
the ``/api/chat`` endpoint which mirrors OpenAI's chat schema closely enough
to share the same ``LlmAdapter`` interface.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.infrastructure.providers.base import LlmAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_MODEL = "llama3.2:1b"
_OLLAMA_TIMEOUT = httpx.Timeout(30.0, connect=2.0)


class OllamaLLMAdapter(LlmAdapter):
    """Chat completion via a self-hosted Ollama server."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        url = (base_url if base_url is not None else _DEFAULT_BASE_URL).rstrip("/")
        if not url:
            raise ProviderConfigurationError("Ollama base_url is not configured")
        self._base_url = url
        self._model = model or _DEFAULT_MODEL

    async def chat_completion(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.4,
        **kwargs: Any,
    ) -> str:
        """Send messages to Ollama's /api/chat and return the assistant text."""
        payload = {
            "model": self._model,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        logger.error("Ollama LLM returned invalid JSON")
                        return ""
                    return (data.get("message") or {}).get("content", "")
                logger.error("Ollama LLM error: status=%d", resp.status_code)
        except httpx.HTTPError:
            logger.exception("Ollama LLM request failed")
        return ""
