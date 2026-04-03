from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.mongo_audit import append_audit_event
from app.domain.voice.models import VoiceScript
from app.domain.voice.schemas import (
    QAPairPublic,
    ScriptCreate,
    ScriptDetailPublic,
    ScriptParsedPublic,
    ScriptPublic,
    ScriptsPublic,
    ScriptUpdate,
)
from app.domain.voice.script_parser import parse_script
from app.infrastructure.authz.enforcer import require_role

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _get_script_or_404(session, script_id: uuid.UUID) -> VoiceScript:
    script = session.get(VoiceScript, script_id)
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


def _to_parsed_public(script: VoiceScript) -> ScriptParsedPublic:
    parsed = parse_script(script.content)
    return ScriptParsedPublic(
        opening_pitch=parsed.opening_pitch,
        qa_pairs=[QAPairPublic(question=p.question, answer=p.answer) for p in parsed.qa_pairs],
        fallback_response=parsed.fallback_response,
        scheduling_question=parsed.scheduling_question,
    )


@router.post("/", response_model=ScriptPublic, dependencies=[Depends(require_role("operator"))])
async def create_script(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: ScriptCreate,
) -> ScriptPublic:
    script = VoiceScript(
        campaign_id=body.campaign_id,
        name=body.name,
        content=body.content,
        created_by=current_user.id,
    )
    session.add(script)
    session.commit()
    session.refresh(script)
    await append_audit_event(
        event_name="script.created",
        workspace_id=workspace_id,
        payload={"id": str(script.id), "name": script.name},
    )
    return ScriptPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
    )


@router.get("/", response_model=ScriptsPublic)
def list_scripts(
    session: SessionDep,
    campaign_id: uuid.UUID | None = None,
) -> ScriptsPublic:
    query = select(VoiceScript).where(VoiceScript.active == True)  # noqa: E712
    if campaign_id:
        query = query.where(VoiceScript.campaign_id == campaign_id)
    scripts = session.exec(query.order_by(VoiceScript.created_at.desc())).all()
    return ScriptsPublic(
        data=[
            ScriptPublic(
                id=s.id, campaign_id=s.campaign_id,
                name=s.name, active=s.active, created_at=s.created_at,
            )
            for s in scripts
        ],
        count=len(scripts),
    )


@router.get("/{script_id}", response_model=ScriptDetailPublic)
def get_script(session: SessionDep, script_id: uuid.UUID) -> ScriptDetailPublic:
    script = _get_script_or_404(session, script_id)
    return ScriptDetailPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
        content=script.content, parsed=_to_parsed_public(script),
    )


@router.get("/{script_id}/preview", response_model=ScriptParsedPublic)
def preview_script(session: SessionDep, script_id: uuid.UUID) -> ScriptParsedPublic:
    script = _get_script_or_404(session, script_id)
    return _to_parsed_public(script)


@router.put("/{script_id}", response_model=ScriptDetailPublic, dependencies=[Depends(require_role("operator"))])
async def update_script(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
    body: ScriptUpdate,
) -> ScriptDetailPublic:
    script = _get_script_or_404(session, script_id)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(script, key, value)
    script.updated_at = datetime.now(timezone.utc)
    session.add(script)
    session.commit()
    session.refresh(script)
    await append_audit_event(
        event_name="script.updated",
        workspace_id=workspace_id,
        payload={"id": str(script.id)},
    )
    return ScriptDetailPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
        content=script.content, parsed=_to_parsed_public(script),
    )


@router.delete("/{script_id}", dependencies=[Depends(require_role("operator"))])
async def delete_script(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
) -> dict[str, str]:
    script = _get_script_or_404(session, script_id)
    script.active = False
    session.add(script)
    session.commit()
    await append_audit_event(
        event_name="script.deleted",
        workspace_id=workspace_id,
        payload={"id": str(script.id)},
    )
    return {"message": "Script deactivated"}
