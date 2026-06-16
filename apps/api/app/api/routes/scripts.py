"""FastAPI router: ``scripts`` endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
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
from app.domain_models import Campaign

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _ensure_campaign_in_workspace(
    session: SessionDep,
    campaign_id: uuid.UUID,
    workspace_id: str,
) -> None:
    campaign = session.exec(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")


def _get_script_or_404(
    session: SessionDep,
    script_id: uuid.UUID,
    workspace_id: str,
) -> VoiceScript:
    script = session.exec(
        select(VoiceScript)
        .join(Campaign, VoiceScript.campaign_id == Campaign.id)
        .where(
            VoiceScript.id == script_id,
            Campaign.workspace_id == workspace_id,
        )
    ).first()
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


@router.post("/", response_model=ScriptPublic, dependencies=[Depends(require_admin)])
async def create_script(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: ScriptCreate,
) -> ScriptPublic:
    """Create script."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="scripts.create",
        request_payload=body.model_dump(mode="json"),
        mutation=lambda: _create_script_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _create_script_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    body: ScriptCreate,
) -> ScriptPublic:
    _ensure_campaign_in_workspace(session, body.campaign_id, workspace_id)
    script = VoiceScript(
        campaign_id=body.campaign_id,
        name=body.name,
        content=body.content,
        created_by=current_user.id,
    )
    session.add(script)
    append_audit_event_to_session(
        session,
        event_name="script.created",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="script",
        resource_id=str(script.id),
        payload={"id": str(script.id), "name": script.name, "campaign_id": str(script.campaign_id)},
    )
    session.commit()
    session.refresh(script)
    return ScriptPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
    )


@router.get("/", response_model=ScriptsPublic)
def list_scripts(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    campaign_id: uuid.UUID | None = None,
) -> ScriptsPublic:
    """Return a list of scripts."""
    query = (
        select(VoiceScript)
        .join(Campaign, VoiceScript.campaign_id == Campaign.id)
        .where(VoiceScript.active == True, Campaign.workspace_id == workspace_id)  # noqa: E712
    )
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
def get_script(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
) -> ScriptDetailPublic:
    """Return script."""
    script = _get_script_or_404(session, script_id, workspace_id)
    return ScriptDetailPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
        content=script.content, parsed=_to_parsed_public(script),
    )


@router.get("/{script_id}/preview", response_model=ScriptParsedPublic)
def preview_script(
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
) -> ScriptParsedPublic:
    """Build a preview of script."""
    script = _get_script_or_404(session, script_id, workspace_id)
    return _to_parsed_public(script)


@router.put("/{script_id}", response_model=ScriptDetailPublic, dependencies=[Depends(require_admin)])
async def update_script(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
    body: ScriptUpdate,
) -> ScriptDetailPublic:
    """Update script."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="scripts.update",
        request_payload={
            "script_id": str(script_id),
            "body": body.model_dump(mode="json", exclude_unset=True),
        },
        mutation=lambda: _update_script_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            script_id=script_id,
            body=body,
        ),
    )


def _update_script_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    script_id: uuid.UUID,
    body: ScriptUpdate,
) -> ScriptDetailPublic:
    script = _get_script_or_404(session, script_id, workspace_id)
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(script, key, value)
    script.updated_at = datetime.now(timezone.utc)
    session.add(script)
    append_audit_event_to_session(
        session,
        event_name="script.updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="script",
        resource_id=str(script.id),
        payload={"id": str(script.id), "changed_fields": sorted(update_data.keys())},
    )
    session.commit()
    session.refresh(script)
    return ScriptDetailPublic(
        id=script.id, campaign_id=script.campaign_id,
        name=script.name, active=script.active, created_at=script.created_at,
        content=script.content, parsed=_to_parsed_public(script),
    )


@router.delete("/{script_id}", dependencies=[Depends(require_admin)])
async def delete_script(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    script_id: uuid.UUID,
    idempotency_key: IdempotencyKeyDep,
) -> dict[str, str]:
    """Delete script."""
    return await run_idempotent_mutation(
        request,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="scripts.delete",
        request_payload={"script_id": str(script_id)},
        mutation=lambda: _delete_script_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            script_id=script_id,
        ),
    )


def _delete_script_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    script_id: uuid.UUID,
) -> dict[str, str]:
    script = _get_script_or_404(session, script_id, workspace_id)
    script.active = False
    session.add(script)
    append_audit_event_to_session(
        session,
        event_name="script.deleted",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="script",
        resource_id=str(script.id),
        payload={"id": str(script.id)},
    )
    session.commit()
    return {"message": "Script deactivated"}
