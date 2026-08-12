"""FastAPI router: ``templates`` endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.core.idempotency import run_idempotent_mutation
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.outreach.token_service import (
    render_template,
    validate_token_definitions,
)
from app.domain.policies.template_guardrail_service import validate_template
from app.domain_models import (
    Template,
    TemplateCreate,
    TemplatePreviewPublic,
    TemplatePreviewRequest,
    TemplatePublic,
    TemplatesPublic,
    TemplateStatus,
    TemplateToken,
    TemplateUpdate,
    TemplateVersion,
    TemplateVersionPublic,
    get_datetime_utc,
)

router = APIRouter(prefix="/templates", tags=["templates"])


def _build_template_public(session: SessionDep, template: Template) -> TemplatePublic:
    version = session.exec(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template.id)
        .order_by(TemplateVersion.version_number.desc())
    ).first()
    current_version = None
    if version:
        current_version = TemplateVersionPublic(
            id=version.id,
            version_number=version.version_number,
            status=version.status,
            guardrail_compliant=version.guardrail_compliant,
            content=version.content,
            subject=version.subject,
        )
    return TemplatePublic(
        id=template.id,
        name=template.name,
        channel=template.channel,
        workspace_id=template.workspace_id,
        current_version=current_version,
    )


@router.get("/", response_model=TemplatesPublic)
def read_templates(session: SessionDep, workspace_id: WorkspaceIdDep, status: TemplateStatus | None = None) -> TemplatesPublic:
    """Return templates."""
    templates = session.exec(select(Template).where(Template.workspace_id == workspace_id)).all()
    data = []
    for template in templates:
        public = _build_template_public(session, template)
        if status and (not public.current_version or public.current_version.status != status):
            continue
        if status == TemplateStatus.published and public.current_version and not public.current_version.guardrail_compliant:
            continue
        data.append(public)
    return TemplatesPublic(data=data, count=len(data))


@router.post("/", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
async def create_template(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: TemplateCreate,
) -> TemplatePublic:
    """Create template."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="templates.create",
        request_payload=body.model_dump(mode="json"),
        mutation=lambda: _create_template_once(
            session=session,
            current_user=current_user,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _create_template_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: str,
    body: TemplateCreate,
) -> TemplatePublic:
    token_errors = validate_token_definitions([token.model_dump() for token in body.tokens])
    if token_errors:
        raise HTTPException(status_code=400, detail=token_errors)
    template = Template(
        workspace_id=workspace_id,
        name=body.name,
        channel=body.channel,
        created_by=current_user.id,
    )
    session.add(template)
    session.flush()

    version = TemplateVersion(
        template_id=template.id,
        workspace_id=workspace_id,
        version_number=1,
        subject=body.subject,
        content=body.content,
    )
    session.add(version)
    for token in body.tokens:
        session.add(TemplateToken(template_id=template.id, **token.model_dump()))
    append_audit_event_to_session(
        session,
        event_name="template_created",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="template",
        resource_id=str(template.id),
        payload={
            "template_id": str(template.id),
            "version_number": version.version_number,
            "channel": template.channel,
            "token_count": len(body.tokens),
        },
    )
    session.commit()
    return _build_template_public(session, template)


@router.patch("/{template_id}", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
async def update_template(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
    body: TemplateUpdate,
) -> TemplatePublic:
    """Update template."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="templates.update",
        request_payload={
            "template_id": str(template_id),
            "body": body.model_dump(mode="json", exclude_unset=True),
        },
        mutation=lambda: _update_template_once(
            session=session,
            current_user=current_user,
            template_id=template_id,
            workspace_id=workspace_id,
            body=body,
        ),
    )


def _update_template_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    workspace_id: str,
    body: TemplateUpdate,
) -> TemplatePublic:
    template = session.exec(select(Template).where(Template.id == template_id, Template.workspace_id == workspace_id)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    latest = session.exec(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
    ).first()
    if not latest:
        raise HTTPException(status_code=404, detail="Template version not found")
    if latest.status == TemplateStatus.published:
        latest = TemplateVersion(
            template_id=template_id,
            workspace_id=workspace_id,
            version_number=latest.version_number + 1,
            subject=body.subject or latest.subject,
            content=body.content or latest.content,
        )
        session.add(latest)
    else:
        if body.subject is not None:
            latest.subject = body.subject
        if body.content is not None:
            latest.content = body.content
        session.add(latest)
    if body.name is not None:
        template.name = body.name
        session.add(template)
    if body.tokens is not None:
        token_errors = validate_token_definitions([token.model_dump() for token in body.tokens])
        if token_errors:
            raise HTTPException(status_code=400, detail=token_errors)
        existing_tokens = session.exec(select(TemplateToken).where(TemplateToken.template_id == template_id)).all()
        for token in existing_tokens:
            session.delete(token)
        for token in body.tokens:
            session.add(TemplateToken(template_id=template_id, **token.model_dump()))
    append_audit_event_to_session(
        session,
        event_name="template_updated",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="template",
        resource_id=str(template_id),
        payload={
            "template_id": str(template_id),
            "version_id": str(latest.id),
            "changed_fields": sorted(body.model_dump(exclude_unset=True).keys()),
        },
    )
    session.commit()
    return _build_template_public(session, template)


@router.post("/{template_id}/clone", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
async def clone_template(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
) -> TemplatePublic:
    """Clone template."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="templates.clone",
        request_payload={"template_id": str(template_id)},
        mutation=lambda: _clone_template_once(
            session=session,
            current_user=current_user,
            template_id=template_id,
            workspace_id=workspace_id,
        ),
    )


def _clone_template_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    workspace_id: str,
) -> TemplatePublic:
    template = session.exec(select(Template).where(Template.id == template_id, Template.workspace_id == workspace_id)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    latest = session.exec(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
    ).first()
    cloned = Template(workspace_id=workspace_id, name=f"{template.name} Copy", channel=template.channel, created_by=current_user.id)
    session.add(cloned)
    session.flush()
    session.add(
        TemplateVersion(
            template_id=cloned.id,
            workspace_id=workspace_id,
            version_number=1,
            subject=latest.subject if latest else None,
            content=latest.content if latest else "",
        )
    )
    for token in session.exec(select(TemplateToken).where(TemplateToken.template_id == template_id)).all():
        session.add(
            TemplateToken(
                template_id=cloned.id,
                name=token.name,
                source_field=token.source_field,
                default_value=token.default_value,
                fallback_behavior=token.fallback_behavior,
            )
        )
    append_audit_event_to_session(
        session,
        event_name="template_cloned",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="template",
        resource_id=str(cloned.id),
        payload={"source_template_id": str(template_id), "cloned_template_id": str(cloned.id)},
    )
    session.commit()
    return _build_template_public(session, cloned)


@router.post("/{template_id}/preview", response_model=TemplatePreviewPublic)
def preview_template(
    *,
    session: SessionDep,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    body: TemplatePreviewRequest,
) -> TemplatePreviewPublic:
    """Build a preview of template."""
    template = session.exec(select(Template).where(Template.id == template_id, Template.workspace_id == workspace_id)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    latest = session.exec(
        select(TemplateVersion)
        .where(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version_number.desc())
    ).first()
    if not latest:
        raise HTTPException(status_code=404, detail="Template version not found")
    tokens = session.exec(select(TemplateToken).where(TemplateToken.template_id == template_id)).all()
    rendered_content, unresolved_tokens = render_template(
        latest.content,
        body.sample_payload,
        [token.model_dump() for token in tokens],
    )
    return TemplatePreviewPublic(rendered_content=rendered_content, unresolved_tokens=unresolved_tokens)


@router.post("/{template_id}/versions/{version_id}/publish", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
async def publish_template(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    idempotency_key: IdempotencyKeyDep,
) -> TemplatePublic:
    """Publish template."""
    return await run_idempotent_mutation(
        request,
        session=session,
        idempotency_key=idempotency_key,
        workspace_id=workspace_id,
        operation="templates.publish",
        request_payload={
            "template_id": str(template_id),
            "version_id": str(version_id),
        },
        mutation=lambda: _publish_template_once(
            session=session,
            current_user=current_user,
            template_id=template_id,
            version_id=version_id,
            workspace_id=workspace_id,
        ),
    )


def _publish_template_once(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    workspace_id: str,
) -> TemplatePublic:
    template = session.exec(select(Template).where(Template.id == template_id, Template.workspace_id == workspace_id)).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    version = session.exec(
        select(TemplateVersion).where(
            TemplateVersion.id == version_id,
            TemplateVersion.template_id == template_id,
            TemplateVersion.workspace_id == workspace_id,
        )
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="Template version not found")
    violations = validate_template(template.channel, version.subject, version.content)
    version.guardrail_report_json = [violation.model_dump() for violation in violations]
    version.guardrail_compliant = len(violations) == 0
    if violations:
        session.add(version)
        session.commit()
        raise HTTPException(status_code=400, detail=[violation.model_dump() for violation in violations])
    version.status = TemplateStatus.published
    version.published_at = get_datetime_utc()
    session.add(version)
    append_audit_event_to_session(
        session,
        event_name="template_published",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="template",
        resource_id=str(template_id),
        payload={"template_id": str(template_id), "version_id": str(version_id)},
    )
    session.commit()
    return _build_template_public(session, template)
