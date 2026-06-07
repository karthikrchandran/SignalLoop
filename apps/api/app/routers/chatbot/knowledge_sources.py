"""ChatBot Hub knowledge source routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import SessionDep
from app.domain.chatbot.indexing_service import (
    build_test_answer,
    index_source,
    reindex_job_id,
)
from app.domain.chatbot.models import (
    ChatbotKnowledgeSource,
    ChatbotKnowledgeSourceType,
    ChatbotKnowledgeStatus,
)
from app.domain.chatbot.repositories import (
    active_index_version,
    count_chunks_for_source,
    get_knowledge_source_by_id,
    list_knowledge_sources,
)
from app.domain.chatbot.schemas import (
    ChatbotKnowledgeSourceCreate,
    ChatbotKnowledgeSourcePublic,
    ChatbotKnowledgeSourcesPublic,
    ChatbotKnowledgeSourceUpdate,
    ChatbotKnowledgeStatusPublic,
    ChatbotReindexPublic,
    ChatbotReindexRequest,
    ChatbotTestBotRequest,
    ChatbotTestBotResponse,
)
from app.infrastructure.rag.document_parser import (
    parse_document,
    validate_document_upload,
)
from app.models import User
from app.routers.chatbot.router import WorkspaceId, require_chatbot_admin

router = APIRouter(tags=["chatbot-knowledge"])


def _progress(row: ChatbotKnowledgeSource) -> int:
    return int((row.config_json or {}).get("progress") or (100 if row.status == ChatbotKnowledgeStatus.ready else 0))


def _public(row: ChatbotKnowledgeSource, session: SessionDep) -> ChatbotKnowledgeSourcePublic:
    return ChatbotKnowledgeSourcePublic(
        id=row.id,
        workspace_id=row.workspace_id,
        source_type=row.source_type,
        title=row.title,
        source_uri=row.source_uri,
        status=row.status,
        index_version=row.index_version,
        chunk_count=count_chunks_for_source(row.workspace_id, session, row.id),
        error_message=row.error_message,
        progress=_progress(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
        indexed_at=row.indexed_at,
    )


def _config_from_body(body: ChatbotKnowledgeSourceCreate | ChatbotKnowledgeSourceUpdate) -> dict[str, object]:
    config: dict[str, object] = {}
    if body.content is not None:
        config["content"] = body.content
    if body.question is not None:
        config["question"] = body.question
    if body.answer is not None:
        config["answer"] = body.answer
    if body.crawl_depth is not None:
        config["crawl_depth"] = body.crawl_depth
    if body.max_pages is not None:
        config["max_pages"] = body.max_pages
    config["progress"] = 0
    return config


@router.get("/knowledge-sources", response_model=ChatbotKnowledgeSourcesPublic)
def list_sources(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotKnowledgeSourcesPublic:
    """List workspace-scoped knowledge sources."""
    rows = list_knowledge_sources(workspace_id, session)
    return ChatbotKnowledgeSourcesPublic(data=[_public(row, session) for row in rows], count=len(rows))


@router.post("/knowledge-sources", response_model=ChatbotKnowledgeSourcePublic, status_code=status.HTTP_201_CREATED)
def create_source(
    body: ChatbotKnowledgeSourceCreate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotKnowledgeSourcePublic:
    """Create a knowledge source."""
    row = ChatbotKnowledgeSource(
        workspace_id=workspace_id,
        source_type=body.source_type,
        title=body.title,
        source_uri=body.source_uri,
        status=ChatbotKnowledgeStatus.pending,
        config_json=_config_from_body(body),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _public(row, session)


@router.post("/knowledge-sources/documents", response_model=ChatbotKnowledgeSourcePublic, status_code=status.HTTP_201_CREATED)
async def upload_document_source(
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
    file: UploadFile = File(...),
) -> ChatbotKnowledgeSourcePublic:
    """Upload and store a document source for background indexing."""
    data = await file.read()
    validate_document_upload(file.filename or "document", len(data))
    try:
        content = parse_document(file.filename or "document", data)
    except RuntimeError:
        content = ""
    row = ChatbotKnowledgeSource(
        workspace_id=workspace_id,
        source_type=ChatbotKnowledgeSourceType.document,
        title=file.filename or "Document",
        source_uri=file.filename,
        status=ChatbotKnowledgeStatus.pending,
        config_json={"filename": file.filename, "content": content, "progress": 0},
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _public(row, session)


@router.put("/knowledge-sources/{source_id}", response_model=ChatbotKnowledgeSourcePublic)
def update_source(
    source_id: uuid.UUID,
    body: ChatbotKnowledgeSourceUpdate,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotKnowledgeSourcePublic:
    """Update a knowledge source and mark it stale."""
    row = get_knowledge_source_by_id(workspace_id, session, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    if body.title is not None:
        row.title = body.title
    if body.source_uri is not None:
        row.source_uri = body.source_uri
    row.config_json = {**(row.config_json or {}), **_config_from_body(body)}
    row.status = ChatbotKnowledgeStatus.stale
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _public(row, session)


@router.delete("/knowledge-sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> None:
    """Delete one source. Chunks remain workspace-scoped and are cleaned by repository stories."""
    row = get_knowledge_source_by_id(workspace_id, session, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    session.delete(row)
    session.commit()


@router.get("/knowledge-sources/{source_id}/status", response_model=ChatbotKnowledgeStatusPublic)
def source_status(
    source_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotKnowledgeStatusPublic:
    """Return indexing status for one source."""
    row = get_knowledge_source_by_id(workspace_id, session, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    return ChatbotKnowledgeStatusPublic(
        id=row.id,
        workspace_id=row.workspace_id,
        status=row.status,
        index_version=row.index_version,
        chunk_count=count_chunks_for_source(workspace_id, session, row.id),
        progress=_progress(row),
        error_message=row.error_message,
        indexed_at=row.indexed_at,
    )


@router.post("/knowledge-sources/{source_id}/reindex", response_model=ChatbotReindexPublic)
async def reindex_source(
    source_id: uuid.UUID,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotReindexPublic:
    """Synchronously index one source for the MVP local path."""
    row = get_knowledge_source_by_id(workspace_id, session, source_id)
    if not row:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    await index_source(session, row)
    return ChatbotReindexPublic(job_id=reindex_job_id(), queued=1, workspace_id=workspace_id, status="complete")


@router.post("/knowledge-sources/reindex", response_model=ChatbotReindexPublic)
async def reindex_sources(
    body: ChatbotReindexRequest,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotReindexPublic:
    """Re-index all or selected workspace sources."""
    rows = list_knowledge_sources(workspace_id, session)
    if body.source_ids:
        wanted = set(body.source_ids)
        rows = [row for row in rows if row.id in wanted]
    for row in rows:
        row.index_version += 1
        await index_source(session, row)
    return ChatbotReindexPublic(job_id=reindex_job_id(), queued=len(rows), workspace_id=workspace_id, status="complete")


@router.post("/test-bot", response_model=ChatbotTestBotResponse)
def test_bot(
    body: ChatbotTestBotRequest,
    workspace_id: WorkspaceId,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_chatbot_admin)],
) -> ChatbotTestBotResponse:
    """Run a grounded Test Bot query against indexed chunks."""
    index_version = body.index_version or active_index_version(workspace_id, session)
    answer, sources, no_kb = build_test_answer(
        workspace_id,
        session,
        question=body.question,
        index_version=index_version,
    )
    return ChatbotTestBotResponse(
        answer=answer,
        ai_disclosure="AI assistant",
        sources=sources,
        no_kb=no_kb,
    )
