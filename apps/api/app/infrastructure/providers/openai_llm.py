"""OpenAI-compatible LLM adapter.

A single adapter class that targets any provider speaking the OpenAI
``/v1/chat/completions`` wire format — OpenAI itself, Together, OpenRouter,
Anthropic-via-proxy, vLLM, LM Studio, etc.  Switching providers is just a
matter of changing ``base_url`` and ``model``.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.infrastructure.providers.base import LlmAdapter
from app.infrastructure.providers.errors import require_provider_key

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_OPENAI_TIMEOUT = httpx.Timeout(30.0, connect=2.0)


class OpenAILLMAdapter(LlmAdapter):
    """Chat completion against any OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = require_provider_key(api_key, "OPENAI_API_KEY")
        self._base_url = (base_url or _DEFAULT_BASE_URL).rstrip("/")
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
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            async with httpx.AsyncClient(timeout=_OPENAI_TIMEOUT) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except ValueError:
                        logger.error("OpenAI LLM returned invalid JSON")
                        return ""
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "")
                logger.error("OpenAI LLM error: status=%d", resp.status_code)
        except httpx.HTTPError:
            logger.exception("OpenAI LLM request failed")
        return ""
