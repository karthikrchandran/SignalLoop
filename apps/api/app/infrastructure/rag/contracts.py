"""Small contracts shared by future ChatBot Hub RAG implementations."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RagContextChunk:
    """Retrieved context passed into the answer generator."""

    chunk_id: UUID
    source_id: UUID
    content: str
    score: float


@dataclass(frozen=True)
class RagRequest:
    """Workspace-scoped RAG request."""

    workspace_id: str
    conversation_id: UUID
    message: str
    index_version: int


@dataclass(frozen=True)
class RagResponse:
    """Grounded bot response with the chunks used to create it."""

    answer: str
    chunks: tuple[RagContextChunk, ...]
    confidence: float
