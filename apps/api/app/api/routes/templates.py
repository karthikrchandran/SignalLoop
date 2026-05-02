from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.audit_events import append_audit_event
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
def create_template(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
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
    session.commit()
    session.refresh(template)

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
    session.commit()
    return _build_template_public(session, template)


@router.patch("/{template_id}", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
def update_template(
    *,
    session: SessionDep,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
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
        session.commit()
        for token in body.tokens:
            session.add(TemplateToken(template_id=template_id, **token.model_dump()))
    session.commit()
    return _build_template_public(session, template)


@router.post("/{template_id}/clone", response_model=TemplatePublic, dependencies=[Depends(require_admin)])
async def clone_template(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
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
    session.commit()
    session.refresh(cloned)
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
    session.commit()
    await append_audit_event(
        event_name="template_cloned",
        workspace_id=workspace_id,
        actor_id=current_user.id,
        resource_type="template",
        resource_id=str(cloned.id),
        payload={"source_template_id": str(template_id), "cloned_template_id": str(cloned.id)},
    )
    return _build_template_public(session, cloned)


@router.post("/{template_id}/preview", response_model=TemplatePreviewPublic)
def preview_template(
    *,
    session: SessionDep,
    template_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    body: TemplatePreviewRequest,
) -> TemplatePreviewPublic:
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
    session: SessionDep,
    template_id: uuid.UUID,
    version_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
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
    session.commit()
    await append_audit_event(
        event_name="template_published",
        workspace_id=workspace_id,
        resource_type="template",
        resource_id=str(template_id),
        payload={"template_id": str(template_id), "version_id": str(version_id)},
    )
    return _build_template_public(session, template)
