"""Knowledge indexing service for ChatBot Hub."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlmodel import Session

from app.domain.chatbot.models import (
    ChatbotKnowledgeSource,
    ChatbotKnowledgeSourceType,
    ChatbotKnowledgeStatus,
)
from app.infrastructure.rag.chunker import chunk_text
from app.infrastructure.rag.embedder import embed_text
from app.infrastructure.vector_store.chunk_repository import (
    replace_chunks,
    search_chunks,
)


def source_text(source: ChatbotKnowledgeSource) -> str:
    """Resolve indexable text from a source row."""
    config = source.config_json or {}
    if source.source_type == ChatbotKnowledgeSourceType.qa_pair:
        return f"Q: {config.get('question', '')}\nA: {config.get('answer', '')}".strip()
    if source.source_type in {ChatbotKnowledgeSourceType.faq, ChatbotKnowledgeSourceType.manual_text}:
        return str(config.get("content") or "")
    if source.source_type == ChatbotKnowledgeSourceType.document:
        return str(config.get("content") or config.get("filename") or "")
    return str(config.get("content") or source.source_uri or "")


async def index_source(session: Session, source: ChatbotKnowledgeSource) -> int:
    """Index one source into workspace-scoped chunks."""
    source.status = ChatbotKnowledgeStatus.indexing
    source.error_message = None
    source.config_json = {**(source.config_json or {}), "progress": 10}
    session.add(source)
    session.commit()
    session.refresh(source)

    try:
        chunks = chunk_text(source_text(source))
        embeddings = await asyncio.gather(*(embed_text(chunk) for chunk in chunks)) if chunks else []
        replace_chunks(
            source.workspace_id,
            session,
            source_id=source.id,
            index_version=source.index_version,
            chunks=chunks,
            embeddings=list(embeddings),
        )
        source.status = ChatbotKnowledgeStatus.ready
        source.error_message = None
        source.indexed_at = datetime.now(timezone.utc)
        source.config_json = {**(source.config_json or {}), "progress": 100}
        session.add(source)
        session.commit()
        return len(chunks)
    except Exception as exc:
        session.rollback()
        source = session.get(ChatbotKnowledgeSource, source.id) or source
        source.status = ChatbotKnowledgeStatus.failed
        source.error_message = str(exc)
        source.config_json = {**(source.config_json or {}), "progress": 100}
        session.add(source)
        session.commit()
        raise


def build_test_answer(
    workspace_id: str,
    session: Session,
    *,
    question: str,
    index_version: int,
) -> tuple[str, list[dict[str, object]], bool]:
    """Build a deterministic grounded Test Bot answer from indexed chunks."""
    chunks = search_chunks(workspace_id, session, query=question, index_version=index_version, limit=3)
    if not chunks:
        return "I do not have indexed knowledge for this workspace yet.", [], True
    best = chunks[0]
    answer = f"Based on {best.source_title}: {best.content[:500]}"
    sources = [
        {
            "source_id": chunk.source_id,
            "source_title": chunk.source_title,
            "chunk_id": chunk.chunk_id,
            "excerpt": chunk.content[:240],
            "score": chunk.score,
        }
        for chunk in chunks
    ]
    return answer, sources, False


def reindex_job_id() -> str:
    """Create a stable job id for reindex responses."""
    return f"kb-{uuid.uuid4()}"
