"""Workspace-scoped chunk repository and retrieval helpers."""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session, delete, select

from app.domain.chatbot.models import ChatbotKnowledgeChunk, ChatbotKnowledgeSource


@dataclass(frozen=True)
class RetrievedChunk:
    """Retrieved chunk with source metadata."""

    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    content: str
    score: float


def replace_chunks(
    workspace_id: str,
    session: Session,
    *,
    source_id: uuid.UUID,
    index_version: int,
    chunks: list[str],
    embeddings: list[list[float]] | None = None,
) -> list[ChatbotKnowledgeChunk]:
    """Replace chunks for one source and index version."""
    session.exec(
        delete(ChatbotKnowledgeChunk).where(
            ChatbotKnowledgeChunk.workspace_id == workspace_id,
            ChatbotKnowledgeChunk.source_id == source_id,
            ChatbotKnowledgeChunk.index_version == index_version,
        )
    )
    rows: list[ChatbotKnowledgeChunk] = []
    dialect_name = session.get_bind().dialect.name
    for index, content in enumerate(chunks):
        embedding = embeddings[index] if embeddings and index < len(embeddings) else None
        row = ChatbotKnowledgeChunk(
            workspace_id=workspace_id,
            source_id=source_id,
            index_version=index_version,
            chunk_index=index,
            content=content,
            token_count=max(1, math.ceil(len(content.split()) * 1.33)),
            embedding=embedding if dialect_name == "postgresql" else None,
        )
        session.add(row)
        rows.append(row)
    return rows


def _lexical_score(query: str, content: str) -> float:
    query_terms = {term.lower() for term in query.split() if len(term) > 2}
    if not query_terms:
        return 0.0
    content_terms = {term.strip(".,!?;:").lower() for term in content.split()}
    overlap = query_terms.intersection(content_terms)
    return round(len(overlap) / len(query_terms), 4)


def _vector_literal(values: list[float]) -> str:
    normalized: list[str] = []
    for value in values:
        number = float(value)
        if not math.isfinite(number):
            number = 0.0
        normalized.append(f"{number:.8f}")
    return f"[{','.join(normalized)}]"


def _as_uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _search_chunks_pgvector(
    workspace_id: str,
    session: Session,
    *,
    query_embedding: list[float],
    index_version: int,
    limit: int,
) -> list[RetrievedChunk]:
    statement = text(
        """
        SELECT
            chunk.id AS chunk_id,
            source.id AS source_id,
            source.title AS source_title,
            chunk.content AS content,
            1.0 / (1.0 + (chunk.embedding <=> CAST(:embedding AS vector))) AS score
        FROM chatbot_knowledge_chunks AS chunk
        JOIN chatbot_knowledge_sources AS source ON chunk.source_id = source.id
        WHERE chunk.workspace_id = :workspace_id
            AND source.workspace_id = :workspace_id
            AND chunk.index_version = :index_version
            AND chunk.embedding IS NOT NULL
        ORDER BY chunk.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
        """
    )
    rows = session.execute(
        statement,
        {
            "workspace_id": workspace_id,
            "index_version": index_version,
            "embedding": _vector_literal(query_embedding),
            "limit": limit,
        },
    ).mappings()
    return [
        RetrievedChunk(
            chunk_id=_as_uuid(row["chunk_id"]),
            source_id=_as_uuid(row["source_id"]),
            source_title=str(row["source_title"]),
            content=str(row["content"]),
            score=round(float(row["score"] or 0.0), 4),
        )
        for row in rows
    ]


def search_chunks(
    workspace_id: str,
    session: Session,
    *,
    query: str,
    query_embedding: list[float] | None = None,
    index_version: int,
    limit: int = 5,
) -> list[RetrievedChunk]:
    """Retrieve chunks scoped by workspace and index version."""
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql" and query_embedding:
        vector_rows = _search_chunks_pgvector(
            workspace_id,
            session,
            query_embedding=query_embedding,
            index_version=index_version,
            limit=limit,
        )
        if vector_rows:
            return vector_rows

    rows = session.exec(
        select(ChatbotKnowledgeChunk, ChatbotKnowledgeSource)
        .join(ChatbotKnowledgeSource, ChatbotKnowledgeChunk.source_id == ChatbotKnowledgeSource.id)
        .where(
            ChatbotKnowledgeChunk.workspace_id == workspace_id,
            ChatbotKnowledgeSource.workspace_id == workspace_id,
            ChatbotKnowledgeChunk.index_version == index_version,
        )
    ).all()
    scored = [
        RetrievedChunk(
            chunk_id=chunk.id,
            source_id=source.id,
            source_title=source.title,
            content=chunk.content,
            score=_lexical_score(query, chunk.content),
        )
        for chunk, source in rows
    ]
    return sorted(scored, key=lambda row: row.score, reverse=True)[:limit]
