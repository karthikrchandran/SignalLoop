from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.domain.audit.audit_events import (
    append_audit_event_to_session,
    audit_actor_role,
)
from app.domain.onboarding.persistence import (
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
from app.domain.onboarding.persistence_service import (
    create_or_resume,
    reconcile_unknown_external_outcome,
    retry,
)
from app.domain.tenants.capabilities import resolve_suite_context
from app.domain.tenants.models import Tenant

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingCreate(BaseModel):
    tenant_key: str = Field(min_length=2, max_length=128)


class OnboardingReconciliation(BaseModel):
    decision: Literal["NOT_ACCEPTED", "OPERATOR_APPROVED_SAFE_RETRY"]
    provider_receipt_id: str = Field(min_length=1, max_length=255)


def _authorize_run_tenant(session: SessionDep, user: CurrentUser, tenant_key: str) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.key == tenant_key)).one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Onboarding tenant not found")
    if user.is_superuser:
        return tenant
    try:
        context = resolve_suite_context(session, user_id=user.id, tenant_id=tenant.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Tenant administration is required") from exc
    if context.tenant_id != tenant.id or "revenueos.admin.manage" not in context.capabilities:
        raise HTTPException(status_code=403, detail="Tenant administration is required")
    return tenant


def _view(session: SessionDep, run: OnboardingRunRecord) -> dict[str, object]:
    stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all()
    evidence = session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id)).all()
    return {"run_id": str(run.id), "tenant_key": run.tenant_key, "status": run.status, "attempt_count": run.attempt_count, "stages": [{"stage": s.stage, "status": s.status, "attempt_count": s.attempt_count, "result_code": s.result_code} for s in stages], "evidence_count": len(evidence)}


@router.post("/runs", status_code=status.HTTP_201_CREATED)
def create_run(*, session: SessionDep, current_user: AdminUser, body: OnboardingCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> dict[str, object]:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        run = create_or_resume(session, body.tenant_key, idempotency_key, str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _view(session, run)


@router.post("/runs/{run_id}/retry")
def retry_run(*, session: SessionDep, _current_user: AdminUser, run_id: uuid.UUID) -> dict[str, object]:
    run = session.get(OnboardingRunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Onboarding run not found")
    return _view(session, retry(session, run))


@router.post("/runs/{run_id}/stages/{stage_id}/reconcile")
def reconcile_run_stage(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    run_id: uuid.UUID,
    stage_id: uuid.UUID,
    body: OnboardingReconciliation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    """Record an operator receipt before an unknown provider outcome can retry."""
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    run = session.get(OnboardingRunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Onboarding run not found")
    tenant = _authorize_run_tenant(session, current_user, run.tenant_key)
    stage = session.get(OnboardingStageRecord, stage_id)
    if stage is None or stage.run_id != run.id:
        raise HTTPException(status_code=404, detail="Onboarding stage not found")
    try:
        reconcile_unknown_external_outcome(session, run, stage, body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    append_audit_event_to_session(
        session,
        event_name="onboarding.external_outcome.reconciled",
        workspace_id=str(tenant.id),
        actor_id=current_user.id,
        actor_role=audit_actor_role(current_user),
        resource_type="onboarding_stage",
        resource_id=str(stage.id),
        payload={
            "run_id": str(run.id),
            "tenant_key": run.tenant_key,
            "decision": body.decision,
            "provider_receipt_id": body.provider_receipt_id,
        },
    )
    session.commit()
    return _view(session, run)


@router.get("/runs/{run_id}")
def read_run(*, session: SessionDep, _current_user: AdminUser, run_id: uuid.UUID) -> dict[str, object]:
    run = session.get(OnboardingRunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Onboarding run not found")
    return _view(session, run)
