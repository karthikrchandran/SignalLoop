from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select

from app.api.deps import AdminUser, SessionDep
from app.domain.onboarding.persistence import (
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
from app.domain.onboarding.persistence_service import create_or_resume, retry

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingCreate(BaseModel):
    tenant_key: str = Field(min_length=2, max_length=128)


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


@router.get("/runs/{run_id}")
def read_run(*, session: SessionDep, _current_user: AdminUser, run_id: uuid.UUID) -> dict[str, object]:
    run = session.get(OnboardingRunRecord, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Onboarding run not found")
    return _view(session, run)
