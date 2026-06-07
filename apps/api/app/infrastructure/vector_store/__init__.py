"""Vector store contracts for ChatBot Hub."""

from app.infrastructure.vector_store.chunk_repository import (
    RetrievedChunk,
    replace_chunks,
    search_chunks,
)
from app.infrastructure.vector_store.pgvector_store import (
    VectorSearchQuery,
    VectorSearchResult,
)

__all__ = [
    "RetrievedChunk",
    "VectorSearchQuery",
    "VectorSearchResult",
    "replace_chunks",
    "search_chunks",
]
