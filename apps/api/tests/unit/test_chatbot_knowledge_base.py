from __future__ import annotations

import asyncio

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.domain.chatbot.indexing_service import build_test_answer, index_source
from app.domain.chatbot.models import (
    ChatbotKnowledgeSource,
    ChatbotKnowledgeSourceType,
    ChatbotKnowledgeStatus,
)
from app.domain.chatbot.repositories import count_chunks_for_source
from app.infrastructure.rag.chunker import chunk_text
from app.infrastructure.rag.document_parser import (
    MAX_DOCUMENT_BYTES,
    validate_document_upload,
)
from app.infrastructure.rag.retriever import retrieve_context
from app.infrastructure.vector_store.chunk_repository import (
    replace_chunks,
    search_chunks,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_document_upload_validation_rejects_unsupported_type_and_large_file() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        validate_document_upload("notes.exe", 10)

    with pytest.raises(ValueError, match="20 MB"):
        validate_document_upload("notes.pdf", MAX_DOCUMENT_BYTES + 1)

    validate_document_upload("notes.txt", MAX_DOCUMENT_BYTES)


def test_chunk_text_respects_overlap_contract() -> None:
    text = " ".join(f"word-{index}" for index in range(900))

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)
    assert chunks[0][-40:] in chunks[1]


def test_chunk_repository_filters_workspace_and_index_version() -> None:
    with _session() as session:
        source_a = ChatbotKnowledgeSource(
            workspace_id="ws-a",
            source_type=ChatbotKnowledgeSourceType.faq,
            title="A FAQ",
        )
        source_b = ChatbotKnowledgeSource(
            workspace_id="ws-b",
            source_type=ChatbotKnowledgeSourceType.faq,
            title="B FAQ",
        )
        session.add(source_a)
        session.add(source_b)
        session.commit()
        session.refresh(source_a)
        session.refresh(source_b)

        replace_chunks("ws-a", session, source_id=source_a.id, index_version=1, chunks=["pricing demo quote"])
        replace_chunks("ws-b", session, source_id=source_b.id, index_version=1, chunks=["pricing leak"])
        session.commit()

        rows = search_chunks("ws-a", session, query="pricing", index_version=1)

        assert [row.source_title for row in rows] == ["A FAQ"]
        assert count_chunks_for_source("ws-a", session, source_a.id) == 1
        assert count_chunks_for_source("ws-a", session, source_b.id) == 0


def test_retriever_passes_query_embedding_to_chunk_search(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    async def fake_embed(text: str) -> list[float]:
        seen["embedded_text"] = text
        return [0.2, 0.4, 0.6]

    def fake_search_chunks(
        workspace_id: str,
        session: Session,
        *,
        query: str,
        query_embedding: list[float] | None,
        index_version: int,
        limit: int = 5,
    ) -> list[object]:
        _ = session
        seen.update(
            {
                "workspace_id": workspace_id,
                "query": query,
                "query_embedding": query_embedding,
                "index_version": index_version,
                "limit": limit,
            }
        )
        return []

    monkeypatch.setattr("app.infrastructure.rag.retriever.embed_text", fake_embed)
    monkeypatch.setattr("app.infrastructure.rag.retriever.search_chunks", fake_search_chunks)

    async def scenario() -> None:
        with _session() as session:
            result = await retrieve_context("ws-a", session, query="pricing", index_version=3, limit=2)

            assert result.best_confidence == 0.0
            assert seen == {
                "embedded_text": "pricing",
                "workspace_id": "ws-a",
                "query": "pricing",
                "query_embedding": [0.2, 0.4, 0.6],
                "index_version": 3,
                "limit": 2,
            }

    asyncio.run(scenario())


def test_index_source_marks_ready_and_test_bot_returns_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_embed(_text: str) -> list[float]:
        return [0.1] * 768

    monkeypatch.setattr("app.domain.chatbot.indexing_service.embed_text", fake_embed)

    async def scenario() -> None:
        with _session() as session:
            source = ChatbotKnowledgeSource(
                workspace_id="ws-a",
                source_type=ChatbotKnowledgeSourceType.faq,
                title="Pricing FAQ",
                config_json={"content": "Pricing starts after a demo request. Ask for a quote."},
            )
            session.add(source)
            session.commit()
            session.refresh(source)

            count = await index_source(session, source)
            session.refresh(source)
            answer, sources, no_kb = build_test_answer(
                "ws-a",
                session,
                question="pricing quote",
                index_version=source.index_version,
            )

            assert count == 1
            assert source.status == ChatbotKnowledgeStatus.ready
            assert source.config_json["progress"] == 100
            assert "Pricing FAQ" in answer
            assert sources[0]["source_title"] == "Pricing FAQ"
            assert no_kb is False

    asyncio.run(scenario())
