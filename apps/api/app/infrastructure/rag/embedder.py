"""Embedding helpers for ChatBot Hub."""

from __future__ import annotations

import hashlib
import os

import httpx

DEFAULT_EMBEDDING_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
EMBEDDING_DIMENSIONS = 768


def deterministic_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Return a deterministic local fallback embedding."""
    digest = hashlib.sha256(text.encode()).digest()
    values: list[float] = []
    for index in range(dimensions):
        byte = digest[index % len(digest)]
        values.append((byte / 127.5) - 1.0)
    return values


async def embed_text(
    text: str,
    *,
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_url: str | None = None,
) -> list[float]:
    """Embed text through Ollama, falling back deterministically when unavailable."""
    base_url = (ollama_url or os.getenv("OLLAMA_URL") or DEFAULT_OLLAMA_URL).rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            response.raise_for_status()
            embedding = response.json().get("embedding")
            if isinstance(embedding, list) and embedding:
                return [float(value) for value in embedding]
    except Exception:
        return deterministic_embedding(text)
    return deterministic_embedding(text)
