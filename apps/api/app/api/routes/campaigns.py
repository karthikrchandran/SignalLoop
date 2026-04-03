from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlmodel import Session, select

from app.api.deps import CurrentUser, SessionDep
from app.api.request_context import IdempotencyKeyDep, WorkspaceIdDep
from app.domain.audit.mongo_audit import append_audit_event
from app.domain.contacts.import_service import parse_csv, preview_rows, validate_rows
from app.domain.contacts.mapping_service import map_row, resolve_mapping
from app.domain.contacts.segment_service import estimate_segment
from app.domain_models import (
    Campaign,
    CampaignChannelStrategy,
    CampaignContactImport,
    CampaignContactStage,
    CampaignCreate,
    CampaignImportPublic,
    CampaignMappingRequest,
    CampaignPublic,
    CampaignStatus,
    CampaignSegment,
    CampaignSegmentCreate,
    CampaignSegmentPublic,
    CampaignSegmentRule,
    CampaignsPublic,
    ImportPreviewPublic,
    ImportRowError,
    OfferPackVersion,
    StrategyPublic,
    StrategyRequest,
    TemplateStatus,
)
from app.infrastructure.authz.enforcer import require_role

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def _get_campaign_or_404(
    session: Session,
    campaign_id: uuid.UUID,
    workspace_id: str,
    *,
    owner_id: uuid.UUID | None = None,
) -> Campaign:
    campaign = session.exec(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if owner_id and campaign.created_by != owner_id:
        raise HTTPException(status_code=403, detail="Campaign does not belong to current user")
    return campaign


def _latest_import(session: Session, campaign_id: uuid.UUID) -> CampaignContactImport:
    campaign_import = session.exec(
        select(CampaignContactImport)
        .where(CampaignContactImport.campaign_id == campaign_id)
        .order_by(CampaignContactImport.created_at.desc())
    ).first()
    if not campaign_import:
        raise HTTPException(status_code=404, detail="Campaign import not found")
    return campaign_import


@router.get("/", response_model=CampaignsPublic)
def read_campaigns(session: SessionDep, workspace_id: WorkspaceIdDep) -> CampaignsPublic:
    campaigns = session.exec(
        select(Campaign).where(Campaign.workspace_id == workspace_id).order_by(Campaign.created_at.desc())
    ).all()
    return CampaignsPublic(
        data=[
            CampaignPublic(
                id=campaign.id,
                name=campaign.name,
                status=campaign.status,
                workspace_id=campaign.workspace_id,
                created_at=campaign.created_at,
            )
            for campaign in campaigns
        ],
        count=len(campaigns),
    )


@router.post("/", response_model=CampaignPublic, dependencies=[Depends(require_role("operator"))])
async def create_campaign(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: CampaignCreate,
) -> CampaignPublic:
    campaign = Campaign(name=body.name, created_by=current_user.id, workspace_id=workspace_id)
    session.add(campaign)
    session.commit()
    session.refresh(campaign)
    await append_audit_event(
        event_name="campaign.created",
        workspace_id=workspace_id,
        payload={"id": str(campaign.id), "name": campaign.name},
    )
    return CampaignPublic(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        workspace_id=campaign.workspace_id,
        created_at=campaign.created_at,
    )


@router.post("/{campaign_id}/contacts/import", response_model=CampaignImportPublic, dependencies=[Depends(require_role("operator"))])
async def import_contacts(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    file: UploadFile = File(...),
) -> CampaignImportPublic:
    _get_campaign_or_404(session, campaign_id, workspace_id, owner_id=current_user.id)
    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="CSV file too large. Maximum size is 10MB")
    headers, rows = parse_csv(file_bytes)
    valid_rows, errors = validate_rows(headers, rows)
    requires_mapping = any(error.row_number == 0 for error in errors)

    campaign_import = CampaignContactImport(
        campaign_id=campaign_id,
        source_file_name=file.filename or "contacts.csv",
        total_rows=len(rows),
        valid_rows=len(valid_rows),
        invalid_rows=len([error for error in errors if error.row_number > 0]),
        headers_json=headers,
        mapping_json=resolve_mapping(headers, {}),
    )
    session.add(campaign_import)
    session.commit()
    session.refresh(campaign_import)

    for index, row in enumerate(rows, start=1):
        row_errors = [error.model_dump() for error in errors if error.row_number == index]
        stage = CampaignContactStage(
            campaign_id=campaign_id,
            import_id=campaign_import.id,
            workspace_id=workspace_id,
            row_number=index,
            is_valid=not row_errors,
            mapped_data_json=row,
            error_json=row_errors,
        )
        session.add(stage)
    session.commit()

    return CampaignImportPublic(
        import_id=campaign_import.id,
        total_rows=campaign_import.total_rows,
        valid_rows=campaign_import.valid_rows,
        invalid_rows=campaign_import.invalid_rows,
        requires_mapping=requires_mapping,
        headers=headers,
        errors=errors,
    )


@router.post("/{campaign_id}/contacts/mapping", response_model=ImportPreviewPublic, dependencies=[Depends(require_role("operator"))])
def persist_mapping(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: CampaignMappingRequest,
) -> ImportPreviewPublic:
    _get_campaign_or_404(session, campaign_id, workspace_id, owner_id=current_user.id)
    campaign_import = _latest_import(session, campaign_id)
    staged_rows = session.exec(
        select(CampaignContactStage).where(CampaignContactStage.import_id == campaign_import.id)
    ).all()
    raw_rows = [row.mapped_data_json for row in staged_rows]
    try:
        effective_mapping = resolve_mapping(campaign_import.headers_json, body.mapping, strict=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    mapped_rows = [map_row(row, effective_mapping) for row in raw_rows]
    valid_rows, errors = validate_rows(campaign_import.headers_json, raw_rows, body.mapping)

    campaign_import.mapping_json = body.mapping
    campaign_import.valid_rows = len(valid_rows)
    campaign_import.invalid_rows = len([error for error in errors if error.row_number > 0])
    session.add(campaign_import)

    for staged_row in staged_rows:
        row_errors = [error.model_dump() for error in errors if error.row_number == staged_row.row_number]
        staged_row.is_valid = not row_errors
        staged_row.error_json = row_errors
        staged_row.mapped_data_json = mapped_rows[staged_row.row_number - 1]
        session.add(staged_row)
    session.commit()

    return ImportPreviewPublic(
        import_id=campaign_import.id,
        preview_rows=[
            {"row_number": index + 1, "data": row}
            for index, row in enumerate(preview_rows(valid_rows))
        ],
        errors=errors,
    )


@router.get("/{campaign_id}/contacts/preview", response_model=ImportPreviewPublic)
def get_import_preview(
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
) -> ImportPreviewPublic:
    _get_campaign_or_404(session, campaign_id, workspace_id, owner_id=current_user.id)
    campaign_import = _latest_import(session, campaign_id)
    staged_rows = session.exec(
        select(CampaignContactStage)
        .where(CampaignContactStage.import_id == campaign_import.id)
        .order_by(CampaignContactStage.row_number)
    ).all()
    valid = [row for row in staged_rows if row.is_valid]
    errors = [ImportRowError.model_validate(error) for row in staged_rows for error in row.error_json]
    return ImportPreviewPublic(
        import_id=campaign_import.id,
        preview_rows=[
            {"row_number": row.row_number, "data": row.mapped_data_json}
            for row in valid[:20]
        ],
        errors=errors,
    )


@router.post("/{campaign_id}/segments", response_model=CampaignSegmentPublic, dependencies=[Depends(require_role("operator"))])
def create_segment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: CampaignSegmentCreate,
) -> CampaignSegmentPublic:
    _get_campaign_or_404(session, campaign_id, workspace_id, owner_id=current_user.id)
    staged_rows = session.exec(
        select(CampaignContactStage).where(
            CampaignContactStage.campaign_id == campaign_id,
            CampaignContactStage.workspace_id == workspace_id,
            CampaignContactStage.is_valid == True,
        )
    ).all()
    rules = [rule.model_dump() for rule in body.rules]
    estimated_count = estimate_segment([row.mapped_data_json for row in staged_rows], rules)

    segment = CampaignSegment(
        campaign_id=campaign_id,
        workspace_id=workspace_id,
        name=body.name,
        estimated_count=estimated_count,
    )
    session.add(segment)
    session.commit()
    session.refresh(segment)

    for rule in body.rules:
        session.add(
            CampaignSegmentRule(
                segment_id=segment.id,
                field_name=rule.field_name,
                operator=rule.operator,
                value=rule.value,
                expression_json=rule.model_dump(),
            )
        )
    session.commit()
    return CampaignSegmentPublic(id=segment.id, name=segment.name, estimated_count=segment.estimated_count)


@router.post("/{campaign_id}/strategy", response_model=StrategyPublic, dependencies=[Depends(require_role("operator"))])
def assign_strategy(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
    _: IdempotencyKeyDep,
    body: StrategyRequest,
) -> StrategyPublic:
    _get_campaign_or_404(session, campaign_id, workspace_id, owner_id=current_user.id)
    if body.offer_pack_version_id:
        version = session.get(OfferPackVersion, body.offer_pack_version_id)
        if not version or version.workspace_id != workspace_id or version.status != TemplateStatus.published or not version.guardrail_compliant:
            raise HTTPException(status_code=400, detail="Only published compliant offer pack versions can be assigned")

    strategy = session.exec(
        select(CampaignChannelStrategy).where(CampaignChannelStrategy.campaign_id == campaign_id)
    ).first()
    if not strategy:
        strategy = CampaignChannelStrategy(campaign_id=campaign_id, workspace_id=workspace_id)
    strategy.offer_pack_id = body.offer_pack_id
    strategy.offer_pack_version_id = body.offer_pack_version_id
    strategy.strategy_json = body.channel_strategy
    session.add(strategy)
    session.commit()
    session.refresh(strategy)
    return StrategyPublic(id=strategy.id, campaign_id=strategy.campaign_id, strategy_json=strategy.strategy_json)


@router.put("/{campaign_id}/pause", dependencies=[Depends(require_role("operator"))])
def pause_campaign(
    session: SessionDep,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
) -> dict[str, str]:
    from app.domain_models import Campaign
    campaign = session.exec(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.active = False
    session.add(campaign)
    session.commit()
    return {"message": f"Campaign '{campaign.name}' paused"}


@router.put("/{campaign_id}/resume", dependencies=[Depends(require_role("operator"))])
def resume_campaign(
    session: SessionDep,
    campaign_id: uuid.UUID,
    workspace_id: WorkspaceIdDep,
) -> dict[str, str]:
    from app.domain_models import Campaign
    campaign = session.exec(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.workspace_id == workspace_id)
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.active = True
    session.add(campaign)
    session.commit()
    return {"message": f"Campaign '{campaign.name}' resumed"}
