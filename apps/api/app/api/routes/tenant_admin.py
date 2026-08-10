from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.branding.models import (
    BrandingLifecycle,
    TenantBrandAsset,
    TenantBrandingVersion,
)
from app.domain.branding.service import BrandAssetValidationError, BrandingService
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import (
    ProductCode,
    RoleBundle,
    SuiteMembership,
    SuiteRoleAssignment,
    Tenant,
    TenantEntitlement,
)

router = APIRouter(prefix="/tenant-admin", tags=["tenant-admin"])


class TenantCreate(BaseModel):
    key: str = Field(min_length=2, max_length=128, pattern=r"^[a-z0-9][a-z0-9-]*$")
    display_name: str = Field(min_length=2, max_length=255)


class EntitlementChange(BaseModel):
    product_code: ProductCode
    status: str = Field(default="ACTIVE", pattern=r"^(ACTIVE|DISABLED)$")


class MembershipCreate(BaseModel):
    user_id: uuid.UUID
    roles: list[RoleBundle] = Field(min_length=1)


class BrandingDraftCreate(BaseModel):
    display_name: str = Field(min_length=3, max_length=80)
    headline: str = Field(min_length=3, max_length=120)
    supporting_copy: str = Field(min_length=3, max_length=300)
    primary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    support_url: HttpUrl | None = None
    privacy_url: HttpUrl | None = None
    legal_url: HttpUrl | None = None


class BrandingAssetUpload(BaseModel):
    mime_type: str
    content_base64: str
    kind: str = Field(default="LOGO", pattern=r"^(LOGO|HERO)$")


def _tenant(session: SessionDep, tenant_id: uuid.UUID) -> Tenant:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _authorize(
    session: SessionDep, user: CurrentUser, tenant_id: uuid.UUID, capability: str
) -> Tenant:
    tenant = _tenant(session, tenant_id)
    if user.is_superuser:
        return tenant
    try:
        context = resolve_suite_context(session, user_id=user.id, tenant_id=tenant_id)
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="Tenant administration is required"
        ) from exc
    if capability not in context.capabilities:
        raise HTTPException(status_code=403, detail="Tenant administration is required")
    return tenant


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
def create_tenant(
    *, session: SessionDep, user: CurrentUser, payload: TenantCreate
) -> Tenant:
    if not user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Platform administration is required"
        )
    if session.exec(select(Tenant).where(Tenant.key == payload.key)).first():
        raise HTTPException(status_code=409, detail="Tenant key already exists")
    tenant = Tenant(key=payload.key, display_name=payload.display_name)
    session.add(tenant)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="tenant.created",
        workspace_id=str(tenant.id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="tenant",
        resource_id=str(tenant.id),
    )
    return tenant


@router.patch("/tenants/{tenant_id}/entitlements")
def change_entitlement(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: EntitlementChange,
) -> TenantEntitlement:
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    row = session.exec(
        select(TenantEntitlement).where(
            TenantEntitlement.tenant_id == tenant_id,
            TenantEntitlement.product_code == payload.product_code,
        )
    ).one_or_none()
    if row is None:
        row = TenantEntitlement(
            tenant_id=tenant_id,
            product_code=payload.product_code,
            status=payload.status,
        )
    else:
        row.status = payload.status
    session.add(row)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="tenant.entitlement.changed",
        workspace_id=str(tenant_id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="entitlement",
        resource_id=str(row.id),
        payload={"product_code": payload.product_code.value, "status": payload.status},
    )
    return row


@router.post("/tenants/{tenant_id}/memberships", status_code=status.HTTP_201_CREATED)
def provision_membership(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: MembershipCreate,
) -> SuiteMembership:
    _authorize(session, user, tenant_id, "tenant.members.manage")
    membership = session.exec(
        select(SuiteMembership).where(
            SuiteMembership.tenant_id == tenant_id,
            SuiteMembership.user_id == payload.user_id,
        )
    ).one_or_none()
    if membership is None:
        membership = SuiteMembership(tenant_id=tenant_id, user_id=payload.user_id)
        session.add(membership)
        session.flush()
    for role in payload.roles:
        existing = session.exec(
            select(SuiteRoleAssignment).where(
                SuiteRoleAssignment.membership_id == membership.id,
                SuiteRoleAssignment.role_bundle == role,
            )
        ).one_or_none()
        if existing is None:
            session.add(
                SuiteRoleAssignment(membership_id=membership.id, role_bundle=role)
            )
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="tenant.membership.provisioned",
        workspace_id=str(tenant_id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="membership",
        resource_id=str(membership.id),
        payload={
            "user_id": str(payload.user_id),
            "roles": [role.value for role in payload.roles],
        },
    )
    return membership


@router.post(
    "/tenants/{tenant_id}/branding/drafts", status_code=status.HTTP_201_CREATED
)
def create_branding_draft(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: BrandingDraftCreate,
):
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    latest = session.exec(
        select(TenantBrandingVersion)
        .where(TenantBrandingVersion.tenant_id == tenant_id)
        .order_by(TenantBrandingVersion.__table__.c.version.desc())  # type: ignore[attr-defined]
    ).first()
    draft = TenantBrandingVersion(
        tenant_id=tenant_id,
        version=(latest.version + 1 if latest else 1),
        lifecycle=BrandingLifecycle.DRAFT,
        created_by=user.id,
        **payload.model_dump(mode="json"),
    )
    session.add(draft)
    session.flush()
    return draft


@router.post("/tenants/{tenant_id}/branding/assets")
def upload_branding_asset(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    payload: BrandingAssetUpload,
):
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
        asset = BrandingService().store_asset(
            tenant_id, payload.mime_type, content, kind=payload.kind, created_by=user.id
        )
    except (ValueError, BrandAssetValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid branding asset") from exc
    db_asset = TenantBrandAsset.model_validate(asset)
    session.add(db_asset)
    session.flush()
    return {
        "id": str(db_asset.id),
        "sha256": db_asset.sha256,
        "byte_count": db_asset.byte_count,
        "mime_type": db_asset.mime_type,
    }


@router.post("/tenants/{tenant_id}/branding/{version_id}/publish")
def publish_branding(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
):
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    draft = session.get(TenantBrandingVersion, version_id)
    if (
        draft is None
        or draft.tenant_id != tenant_id
        or draft.lifecycle != BrandingLifecycle.VALIDATED
    ):
        raise HTTPException(
            status_code=409, detail="Only a validated tenant draft can be published"
        )
    previous = session.exec(
        select(TenantBrandingVersion).where(
            TenantBrandingVersion.tenant_id == tenant_id,
            TenantBrandingVersion.lifecycle == BrandingLifecycle.PUBLISHED,
        )
    ).all()
    for old in previous:
        old.lifecycle = BrandingLifecycle.SUPERSEDED
    draft.lifecycle = BrandingLifecycle.PUBLISHED
    draft.published_by = user.id
    draft.published_at = datetime.now(timezone.utc)
    session.add(draft)
    session.flush()
    append_audit_event_to_session(
        session,
        event_name="tenant.branding.published",
        workspace_id=str(tenant_id),
        actor_id=user.id,
        actor_role=audit_actor_role(user),
        resource_type="branding",
        resource_id=str(draft.id),
        payload={"version": draft.version},
    )
    return draft


@router.post("/tenants/{tenant_id}/branding/{version_id}/validate")
def validate_branding(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
):
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    draft = session.get(TenantBrandingVersion, version_id)
    if (
        draft is None
        or draft.tenant_id != tenant_id
        or draft.lifecycle != BrandingLifecycle.DRAFT
    ):
        raise HTTPException(status_code=409, detail="Only a draft can be validated")
    if not draft.support_url or not draft.privacy_url or not draft.legal_url:
        raise HTTPException(
            status_code=422, detail="Support, privacy, and legal links are required"
        )
    draft.lifecycle = BrandingLifecycle.VALIDATED
    draft.validated_by = user.id
    session.add(draft)
    session.flush()
    return draft


@router.post("/tenants/{tenant_id}/branding/{version_id}/rollback")
def rollback_branding(
    *,
    session: SessionDep,
    user: CurrentUser,
    tenant_id: uuid.UUID,
    version_id: uuid.UUID,
):
    _authorize(session, user, tenant_id, "tenant.settings.manage")
    source = session.get(TenantBrandingVersion, version_id)
    if (
        source is None
        or source.tenant_id != tenant_id
        or source.lifecycle
        not in {BrandingLifecycle.PUBLISHED, BrandingLifecycle.SUPERSEDED}
    ):
        raise HTTPException(status_code=404, detail="Branding version not found")
    latest = session.exec(
        select(TenantBrandingVersion)
        .where(TenantBrandingVersion.tenant_id == tenant_id)
        .order_by(TenantBrandingVersion.__table__.c.version.desc())  # type: ignore[attr-defined]
    ).first()
    if latest is None:
        raise HTTPException(status_code=409, detail="No branding history exists")
    draft = TenantBrandingVersion(
        tenant_id=tenant_id,
        version=latest.version + 1,
        lifecycle=BrandingLifecycle.VALIDATED,
        display_name=source.display_name,
        product_name=source.product_name,
        headline=source.headline,
        supporting_copy=source.supporting_copy,
        primary_color=source.primary_color,
        secondary_color=source.secondary_color,
        support_url=source.support_url,
        privacy_url=source.privacy_url,
        legal_url=source.legal_url,
        logo_asset_id=source.logo_asset_id,
        hero_asset_id=source.hero_asset_id,
        created_by=user.id,
    )
    session.add(draft)
    session.flush()
    return publish_branding(
        session=session, user=user, tenant_id=tenant_id, version_id=draft.id
    )
