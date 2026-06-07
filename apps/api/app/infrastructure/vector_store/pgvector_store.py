"""pgvector search contracts for the ChatBot Hub foundation slice."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VectorSearchQuery:
    """Workspace-scoped vector search input."""

    workspace_id: str
    embedding: tuple[float, ...]
    index_version: int
    limit: int = 5


@dataclass(frozen=True)
class VectorSearchResult:
    """One workspace-scoped vector search result."""

    chunk_id: UUID
    source_id: UUID
    content: str
    score: float
