from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.revenue_intelligence.models import Intervention
from app.domain.revenue_intelligence.service import RevenueIntelligenceService, TenantScopeError
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import Tenant

router = APIRouter(prefix="/revenueos/interventions", tags=["revenueos-interventions"])
service = RevenueIntelligenceService()


class InterventionAction(BaseModel):
    actor: str = Field(min_length=1)


class InterventionProposal(BaseModel):
    signal_id: UUID
    action: str = Field(min_length=1)
    consent_verified: bool
    policy_allowed: bool
    evidence_refs: list[str] = Field(min_length=1)


def _tenant_context(session: SessionDep, current_user: CurrentUser, tenant_key: str | None, capability: str):
    if not tenant_key:
        raise HTTPException(status_code=400, detail="X-Tenant-Key is required")
    tenant = session.exec(select(Tenant).where(Tenant.key == tenant_key)).one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    try:
        context = resolve_suite_context(session, user_id=current_user.id, tenant_id=tenant.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Suite access denied") from exc
    if capability not in context.capabilities:
        raise HTTPException(status_code=403, detail="RevenueOS capability required")
    return tenant_key, context


def _public(item: Intervention) -> dict[str, object]:
    return {"id": str(item.id), "tenant_key": item.tenant_key, "signal_id": str(item.signal_id), "action": item.action, "status": item.status, "evidence_refs": list(item.evidence_refs), "created_at": item.created_at}


@router.get("")
def list_interventions(session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key")):
    tenant_key, _ = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    return {"data": [_public(item) for item in service.list_interventions(tenant_key=tenant_key)]}


@router.post("", status_code=status.HTTP_201_CREATED)
def propose_intervention(body: InterventionProposal, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    tenant_key, _ = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        item = service.propose_intervention(tenant_key=tenant_key, signal_id=body.signal_id, action=body.action, consent_verified=body.consent_verified, policy_allowed=body.policy_allowed, evidence_refs=tuple(body.evidence_refs), idempotency_key=idempotency_key)
        return _public(item)
    except (ValueError, TenantScopeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{intervention_id}")
def get_intervention(intervention_id: UUID, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key")):
    tenant_key, _ = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    try:
        return _public(service.get_intervention(tenant_key=tenant_key, intervention_id=intervention_id))
    except TenantScopeError as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc


def _transition(target: str, intervention_id: UUID, body: InterventionAction, idempotency_key: str | None, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None):
    tenant_key, context = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        return _public(service.transition_intervention(tenant_key=tenant_key, intervention_id=intervention_id, target=target, actor=body.actor, idempotency_key=idempotency_key))
    except TenantScopeError as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{intervention_id}/approve")
def approve(intervention_id: UUID, body: InterventionAction, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return _transition("approved", intervention_id, body, idempotency_key, session, current_user, x_tenant_key)


@router.post("/{intervention_id}/reject")
def reject(intervention_id: UUID, body: InterventionAction, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return _transition("rejected", intervention_id, body, idempotency_key, session, current_user, x_tenant_key)


@router.post("/{intervention_id}/cancel")
def cancel(intervention_id: UUID, body: InterventionAction, session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    return _transition("cancelled", intervention_id, body, idempotency_key, session, current_user, x_tenant_key)


@router.post("/{intervention_id}/outcome")
def outcome(intervention_id: UUID, body: dict[str, object], session: SessionDep, current_user: CurrentUser, x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"), idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    tenant_key, _ = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        result = service.record_outcome(tenant_key=tenant_key, intervention_id=intervention_id, status=str(body.get("status", "")), evidence_refs=tuple(str(ref) for ref in body.get("evidence_refs", [])), idempotency_key=idempotency_key)
        return {"id": str(result.id), "intervention_id": str(result.intervention_id), "status": result.status, "evidence_refs": list(result.evidence_refs), "recorded_at": result.recorded_at}
    except (ValueError, TenantScopeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
