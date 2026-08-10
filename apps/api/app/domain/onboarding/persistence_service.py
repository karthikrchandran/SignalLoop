from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from .manifest import load_phase1_manifests
from .models import OnboardingStage, StageStatus
from .persistence import (
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
from .providers import FakeProviderHub


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_run(session: Session, run_id: str) -> OnboardingRunRecord | None:
    return session.get(OnboardingRunRecord, run_id)


def create_or_resume(session: Session, tenant_key: str, idempotency_key: str, actor: str | None = None) -> OnboardingRunRecord:
    if tenant_key not in load_phase1_manifests():
        raise ValueError(f"unsupported phase1 tenant: {tenant_key}")
    run = session.exec(select(OnboardingRunRecord).where(OnboardingRunRecord.idempotency_key == idempotency_key)).first()
    if run is None:
        run = OnboardingRunRecord(tenant_key=tenant_key, idempotency_key=idempotency_key, actor=actor)
        session.add(run)
        session.flush()
        for stage in OnboardingStage:
            session.add(OnboardingStageRecord(run_id=run.id, stage=stage.value))
    execute(session, run, FakeProviderHub())
    session.commit()
    session.refresh(run)
    return run


def retry(session: Session, run: OnboardingRunRecord) -> OnboardingRunRecord:
    execute(session, run, FakeProviderHub())
    session.commit()
    session.refresh(run)
    return run


def execute(session: Session, run: OnboardingRunRecord, providers: FakeProviderHub) -> None:
    run.attempt_count += 1
    run.status = StageStatus.RUNNING.value
    stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id).order_by(OnboardingStageRecord.id)).all()
    for stage in stages:
        if stage.status == StageStatus.SUCCEEDED.value:
            continue
        # ACTIVE is intentionally never entered by the acceptance API.
        if stage.stage == OnboardingStage.ACTIVE.value:
            continue
        stage.status = StageStatus.RUNNING.value
        stage.attempt_count += 1
        stage.started_at = stage.started_at or _now()
        outcome = "UNCHANGED"
        if stage.stage == OnboardingStage.TENANT_DRAFTED.value:
            outcome = providers.provision_tenant(run.tenant_key)
        elif stage.stage == OnboardingStage.PRODUCTS_ASSIGNED.value:
            outcome = "UPDATED"
        stage.status = StageStatus.SUCCEEDED.value
        stage.result_code = outcome
        stage.completed_at = _now()
        evidence = OnboardingEvidenceRecord(
            run_id=run.id, stage=stage.stage, result_code=outcome,
            digest=f"{run.id}:{stage.stage}:{outcome}", payload={"tenant_key": run.tenant_key},
        )
        if not session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id, OnboardingEvidenceRecord.stage == stage.stage, OnboardingEvidenceRecord.digest == evidence.digest)).first():
            session.add(evidence)
    run.status = StageStatus.SUCCEEDED.value
    run.updated_at = _now()
