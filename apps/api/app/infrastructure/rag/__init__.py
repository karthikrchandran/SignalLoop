"""RAG infrastructure contracts for ChatBot Hub."""

from app.infrastructure.rag.chunker import chunk_text
from app.infrastructure.rag.contracts import RagContextChunk, RagRequest, RagResponse
from app.infrastructure.rag.embedder import embed_text
from app.infrastructure.rag.retriever import RetrievalResult, retrieve_context

__all__ = [
    "RagContextChunk",
    "RagRequest",
    "RagResponse",
    "RetrievalResult",
    "chunk_text",
    "embed_text",
    "retrieve_context",
]
