from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import func, select

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
from app.domain.support_access.service import (
    SupportAccessDenied,
    resolve_support_context,
)
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import (
    ProductCode,
    ProductInstallation,
    SuiteProjectionOutbox,
    Tenant,
    TenantEntitlement,
    TenantWorkspaceBinding,
)
from app.domain_models import (
    ProviderCapability,
    ProviderCredential,
    WorkspaceProviderSelection,
)

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
    support_grant_id: str | None = None,
) -> Tenant:
    if not tenant_key:
        raise HTTPException(status_code=400, detail="X-Tenant-Key is required")
    tenant = session.exec(select(Tenant).where(Tenant.key == tenant_key)).one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if support_grant_id:
        try:
            grant_id = UUID(support_grant_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        entitlement = session.exec(
            select(TenantEntitlement).where(
                TenantEntitlement.tenant_id == tenant.id,
                TenantEntitlement.product_code == ProductCode.REVENUE_OS,
                TenantEntitlement.status == "ACTIVE",
            )
        ).one_or_none()
        if tenant.status != "ACTIVE" or entitlement is None:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            resolve_support_context(
                session,
                grant_id=grant_id,
                operator_user_id=current_user.id,
                tenant_id=tenant.id,
                required_capability=capability,
            )
            session.commit()
        except SupportAccessDenied as exc:
            session.commit()
            raise HTTPException(status_code=404, detail="Not found") from exc
        return tenant
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


def _status_counts(
    rows: list[RevenueInterventionDispatch] | list[SuiteProjectionOutbox],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return counts


def _grouped_status_counts(
    session: SessionDep,
    model: type[RevenueInterventionDispatch] | type[SuiteProjectionOutbox],
    tenant_id: UUID,
) -> dict[str, int]:
    """Return tenant-local aggregate state without loading operational histories."""
    rows = session.exec(
        select(model.status, func.count())
        .where(model.tenant_id == tenant_id)
        .group_by(model.status)
    ).all()
    return {str(status): int(count) for status, count in rows}


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _operational_readiness(
    dispatch_counts: dict[str, int],
    projection_counts: dict[str, int],
    setup_blockers: list[str],
) -> dict[str, object]:
    """Summarize durable recovery state without exposing provider error detail."""
    blocked_reasons = list(setup_blockers)
    blocked_reasons.extend(
        reason
        for status, reason in (
            ("CONFIGURATION_BLOCKED", "PROJECTION_CONFIGURATION_BLOCKED"),
            ("DEAD_LETTER", "PROJECTION_DEAD_LETTER"),
        )
        if projection_counts.get(status, 0)
    )
    blocked_reasons.extend(
        reason
        for status, reason in (
            ("DEAD_LETTER", "DISPATCH_DEAD_LETTER"),
            ("UNKNOWN_PROVIDER_OUTCOME", "DISPATCH_PROVIDER_OUTCOME_UNKNOWN"),
        )
        if dispatch_counts.get(status, 0)
    )
    if blocked_reasons:
        return {
            "status": "BLOCKED",
            "requires_operator_action": True,
            "reasons": blocked_reasons,
        }

    degraded_reasons = [
        reason
        for status, reason in (
            ("PENDING", "PROJECTION_BACKLOG"),
            ("RETRY_SCHEDULED", "PROJECTION_RETRY_SCHEDULED"),
            ("IN_FLIGHT", "PROJECTION_EXECUTING"),
        )
        if projection_counts.get(status, 0)
    ]
    degraded_reasons.extend(
        reason
        for status, reason in (
            ("PENDING", "DISPATCH_BACKLOG"),
            ("RETRY_SCHEDULED", "DISPATCH_RETRY_SCHEDULED"),
            ("IN_FLIGHT", "DISPATCH_EXECUTING"),
        )
        if dispatch_counts.get(status, 0)
    )
    if degraded_reasons:
        return {
            "status": "DEGRADED",
            "requires_operator_action": False,
            "reasons": degraded_reasons,
        }
    return {"status": "READY", "requires_operator_action": False, "reasons": []}


@router.get("")
def list_interventions(
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read", x_support_grant_id)
    store = RevenueInterventionStore(session)
    return {"data": [_public(tenant, item) for item in store.list_interventions(tenant_id=tenant.id)]}


@router.post("", status_code=status.HTTP_201_CREATED)
def propose_intervention(
    body: InterventionProposal,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
    store = RevenueInterventionStore(session)
    all_rows = store.list_dispatches(tenant_id=tenant.id)
    requested_status = dispatch_status.upper() if dispatch_status else None
    rows = (
        store.list_dispatches(tenant_id=tenant.id, status=requested_status)
        if requested_status
        else all_rows
    )
    return {
        "tenant_key": tenant.key,
        "counts": _status_counts(all_rows),
        "data": [_dispatch_public(row) for row in rows],
    }


@router.get("/operations/health")
def operational_health(
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    """Return tenant-scoped execution readiness and durable failure state."""
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
    dispatch_counts = _grouped_status_counts(session, RevenueInterventionDispatch, tenant.id)
    projection_counts = _grouped_status_counts(session, SuiteProjectionOutbox, tenant.id)
    installations = list(
        session.exec(
            select(ProductInstallation).where(ProductInstallation.tenant_id == tenant.id)
        ).all()
    )
    signal_loop = next((item for item in installations if item.product_code == ProductCode.SIGNAL_LOOP), None)
    setup_blockers: list[str] = []
    if signal_loop is None:
        setup_blockers.append("SIGNAL_LOOP_INSTALLATION_MISSING")
    elif not (
        signal_loop.status == "ACTIVE"
        and signal_loop.local_identifier
        and signal_loop.projection_endpoint
        and signal_loop.workload_key_id
        and signal_loop.workload_key_status == "ACTIVE"
    ):
        setup_blockers.append("SIGNAL_LOOP_INSTALLATION_NOT_READY")
    else:
        binding = session.exec(
            select(TenantWorkspaceBinding).where(
                TenantWorkspaceBinding.tenant_id == tenant.id,
                TenantWorkspaceBinding.installation_id == signal_loop.id,
                TenantWorkspaceBinding.status == "ACTIVE",
            )
        ).one_or_none()
        if binding is None:
            setup_blockers.append("SIGNAL_LOOP_WORKSPACE_BINDING_MISSING")
        elif binding.workspace_id != signal_loop.local_identifier:
            setup_blockers.append("SIGNAL_LOOP_WORKSPACE_BINDING_MISMATCH")
        else:
            selection = session.exec(
                select(WorkspaceProviderSelection).where(
                    WorkspaceProviderSelection.workspace_id == binding.workspace_id,
                    WorkspaceProviderSelection.capability == ProviderCapability.email,
                    WorkspaceProviderSelection.is_active == True,  # noqa: E712
                )
            ).one_or_none()
            if selection is None:
                setup_blockers.append("SIGNAL_LOOP_PROVIDER_READINESS_UNAVAILABLE")
            else:
                credential_count = session.exec(
                    select(func.count())
                    .select_from(ProviderCredential)
                    .where(
                        ProviderCredential.workspace_id == binding.workspace_id,
                        ProviderCredential.provider == selection.provider,
                        ProviderCredential.channel == "email",
                        ProviderCredential.is_active == True,  # noqa: E712
                    )
                ).one()
                if credential_count == 0:
                    setup_blockers.append("SIGNAL_LOOP_PROVIDER_READINESS_UNAVAILABLE")
    return {
        "tenant_key": tenant.key,
        "readiness": _operational_readiness(dispatch_counts, projection_counts, setup_blockers),
        "dispatches": {
            "counts": dispatch_counts,
            "policy_denial_count": dispatch_counts.get("POLICY_DENIED", 0),
            "dead_letter_count": dispatch_counts.get("DEAD_LETTER", 0),
        },
        "projections": {
            "counts": projection_counts,
            "unacknowledged_count": sum(
                count for item_status, count in projection_counts.items() if item_status != "ACKNOWLEDGED"
            ),
            "dead_letter_count": projection_counts.get("DEAD_LETTER", 0),
            "configuration_blocked_count": projection_counts.get("CONFIGURATION_BLOCKED", 0),
        },
        "installations": [
            {
                "product_code": _enum_value(item.product_code),
                "status": item.status,
                "projection_ready": bool(
                    item.status == "ACTIVE"
                    and item.projection_endpoint
                    and item.workload_key_id
                    and item.workload_key_status == "ACTIVE"
                ),
            }
            for item in installations
        ],
    }


@router.post("/operations/dispatches/{dispatch_id}/retry")
def retry_dispatch(
    dispatch_id: UUID,
    body: InterventionAction,
    session: SessionDep,
    current_user: CurrentUser,
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.essentials.read", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
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
    x_support_grant_id: Annotated[str | None, Header(alias="X-Support-Grant-Id")] = None,
):
    tenant = _tenant_context(session, current_user, x_tenant_key, "revenueos.admin.manage", x_support_grant_id)
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
