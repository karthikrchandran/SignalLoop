from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.domain.revenue_intelligence.persistence import (
    RevenueInterventionConflict,
    RevenueInterventionNotFound,
    RevenueInterventionStore,
)
from app.domain.revenue_intelligence.persistence_models import (
    RevenueInterventionDispatch,
    RevenueInterventionOutcome,
    RevenueInterventionRecord,
)
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


class InterventionOutcome(BaseModel):
    status: str = Field(min_length=1)
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


def _actor_subject(body: InterventionAction, current_user: CurrentUser) -> str:
    """Bind audit attribution to authentication, rejecting caller impersonation."""
    actor = str(current_user.id)
    if body.actor is not None and body.actor.strip() != actor:
        raise HTTPException(status_code=400, detail="actor must match the authenticated user")
    return actor


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


def _outcome_public(tenant: Tenant, item: RevenueInterventionOutcome) -> dict[str, object]:
    return {
        "id": str(item.id),
        "tenant_key": tenant.key,
        "intervention_id": str(item.intervention_id),
        "status": item.status,
        "evidence_refs": list(item.evidence_refs),
        "created_at": item.created_at,
    }


def _dispatch_public(item: RevenueInterventionDispatch) -> dict[str, object]:
    return {
        "id": str(item.id),
        "intervention_id": str(item.intervention_id),
        "status": item.status,
        "attempt_count": item.attempt_count,
        "next_attempt_at": item.next_attempt_at,
        "provider": item.provider,
        "last_error": item.last_error,
        "dead_letter_reason": item.dead_letter_reason,
        "updated_at": item.updated_at,
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


@router.get("/operations/dispatches")
def list_dispatches(
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    dispatch_status: str | None = Query(default=None, alias="status"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    store = RevenueInterventionStore(session)
    all_rows = store.list_dispatches(tenant_id=tenant.id)
    requested_status = dispatch_status.upper() if dispatch_status else None
    rows = (
        store.list_dispatches(tenant_id=tenant.id, status=requested_status)
        if requested_status
        else all_rows
    )
    counts: dict[str, int] = {}
    for row in all_rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return {
        "tenant_key": tenant.key,
        "counts": counts,
        "data": [_dispatch_public(row) for row in rows],
    }


@router.post("/operations/dispatches/{dispatch_id}/retry")
def retry_dispatch(
    dispatch_id: UUID,
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
        item = RevenueInterventionStore(session).retry_dead_letter_dispatch(
            tenant_id=tenant.id,
            dispatch_id=dispatch_id,
            actor_id=_actor_subject(body, current_user),
            idempotency_key=idempotency_key,
        )
        return _dispatch_public(item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Dispatch not found") from exc
    except RevenueInterventionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
            actor_id=_actor_subject(body, current_user),
            idempotency_key=idempotency_key,
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
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        item = RevenueInterventionStore(session).reject_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention_id,
            actor_id=_actor_subject(body, current_user),
            idempotency_key=idempotency_key,
        )
        return _public(tenant, item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc
    except RevenueInterventionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{intervention_id}/cancel")
def cancel(
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
        item = RevenueInterventionStore(session).cancel_intervention(
            tenant_id=tenant.id,
            intervention_id=intervention_id,
            actor_id=_actor_subject(body, current_user),
            idempotency_key=idempotency_key,
        )
        return _public(tenant, item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc
    except RevenueInterventionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{intervention_id}/outcome")
def outcome(
    intervention_id: UUID,
    body: InterventionOutcome,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage")
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        item = RevenueInterventionStore(session).record_outcome(
            tenant_id=tenant.id,
            intervention_id=intervention_id,
            status=body.status,
            evidence_refs=body.evidence_refs,
            actor_id=str(current_user.id),
            idempotency_key=idempotency_key,
        )
        return _outcome_public(tenant, item)
    except RevenueInterventionNotFound as exc:
        raise HTTPException(status_code=404, detail="Intervention not found") from exc
    except RevenueInterventionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
