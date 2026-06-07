"""Runtime retrieval helpers for ChatBot Hub."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.infrastructure.rag.embedder import embed_text
from app.infrastructure.vector_store.chunk_repository import (
    RetrievedChunk,
    search_chunks,
)


@dataclass(frozen=True)
class RetrievalResult:
    """Retrieved context and aggregate confidence."""

    chunks: list[RetrievedChunk]
    best_confidence: float


async def retrieve_context(
    workspace_id: str,
    session: Session,
    *,
    query: str,
    index_version: int,
    limit: int = 5,
) -> RetrievalResult:
    """Embed the visitor message and retrieve scoped knowledge chunks."""
    query_embedding = await embed_text(query)
    chunks = search_chunks(
        workspace_id,
        session,
        query=query,
        query_embedding=query_embedding,
        index_version=index_version,
        limit=limit,
    )
    best = max((chunk.score for chunk in chunks), default=0.0)
    return RetrievalResult(chunks=chunks, best_confidence=best)
