from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.revenue_intelligence.persistence import (
    RevenueInterventionConflict,
    RevenueInterventionNotFound,
    RevenueInterventionStore,
)
from app.domain.revenue_intelligence.persistence_models import RevenueInterventionRecord
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import Tenant

router = APIRouter(prefix="/revenueos/interventions", tags=["revenueos-interventions"])


class InterventionAction(BaseModel):
    actor: str | None = None


class InterventionProposal(BaseModel):
    signal_id: UUID
    action: str = Field(min_length=1)
    action_payload: dict[str, object] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(min_length=1)


def _tenant_context(
    session: SessionDep,
    current_user: CurrentUser,
    tenant_key: str | None,
    capability: str,
) -> Tenant:
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
    return tenant


def _public(tenant: Tenant, item: RevenueInterventionRecord) -> dict[str, object]:
    return {
        "id": str(item.id),
        "tenant_key": tenant.key,
        "signal_id": str(item.signal_id),
        "action": item.action,
        "action_payload": item.action_payload,
        "status": item.status,
        "denial_reason": item.denial_reason,
        "evidence_refs": list(item.evidence_refs),
        "created_at": item.created_at,
    }


@router.get("")
def list_interventions(
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    store = RevenueInterventionStore(session)
    return {"data": [_public(tenant, item) for item in store.list_interventions(tenant_id=tenant.id)]}


@router.post("", status_code=status.HTTP_201_CREATED)
def propose_intervention(
    body: InterventionProposal,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        item = RevenueInterventionStore(session).propose_intervention(
            tenant_id=tenant.id,
            signal_id=body.signal_id,
            action=body.action,
            action_payload=body.action_payload,
            evidence_refs=body.evidence_refs,
            idempotency_key=idempotency_key,
        )
        return _public(tenant, item)
    except RevenueInterventionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (RevenueInterventionNotFound, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{intervention_id}")
def get_intervention(
    intervention_id: UUID,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read")
    try:
        item = RevenueInterventionStore(session).get_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention_id,
        )
        return _public(tenant, item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc


@router.post("/{intervention_id}/approve")
def approve(
    intervention_id: UUID,
    body: InterventionAction,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        item = RevenueInterventionStore(session).approve_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention_id,
            actor_id=body.actor or str(current_user.id),
        )
        return _public(tenant, item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{intervention_id}/reject")
def reject(
    intervention_id: UUID,
    body: InterventionAction,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _unsupported_transition(
        session=session,
        current_user=current_user,
        x_tenant_key=x_tenant_key,
        idempotency_key=idempotency_key,
        intervention_id=intervention_id,
        actor=body.actor,
    )
    raise HTTPException(status_code=501, detail="Durable rejection is not implemented yet")


@router.post("/{intervention_id}/cancel")
def cancel(
    intervention_id: UUID,
    body: InterventionAction,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _unsupported_transition(
        session=session,
        current_user=current_user,
        x_tenant_key=x_tenant_key,
        idempotency_key=idempotency_key,
        intervention_id=intervention_id,
        actor=body.actor,
    )
    raise HTTPException(status_code=501, detail="Durable cancellation is not implemented yet")


@router.post("/{intervention_id}/outcome")
def outcome(
    intervention_id: UUID,
    body: dict[str, object],
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    _unsupported_transition(
        session=session,
        current_user=current_user,
        x_tenant_key=x_tenant_key,
        idempotency_key=idempotency_key,
        intervention_id=intervention_id,
        actor=str(body.get("actor", "")),
    )
    raise HTTPException(status_code=501, detail="Durable outcome recording is not implemented yet")


def _unsupported_transition(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None,
    idempotency_key: str | None,
    intervention_id: UUID,
    actor: str | None,
) -> None:
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    RevenueInterventionStore(session).get_intervention(
        tenant_id=tenant.id,
        intervention_id=intervention_id,
    )
    if actor is not None:
        actor.strip()
