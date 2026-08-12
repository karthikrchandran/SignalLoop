from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Protocol

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


class ScopedCanary(Protocol):
    """Tenant-scoped integration verification without CRM payload access."""

    def verify(self, tenant_key: str) -> tuple[str, dict[str, int]]: ...


class DeterministicScopedCanary:
    def verify(self, tenant_key: str) -> tuple[str, dict[str, int]]:
        return "CANARY_OK", {"missing": 0, "unexpected": 0}


def create_or_resume(
    session: Session,
    tenant_key: str,
    idempotency_key: str,
    actor: str | None = None,
    *,
    providers: FakeProviderHub | None = None,
    canary: ScopedCanary | None = None,
) -> OnboardingRunRecord:
    if tenant_key not in load_phase1_manifests():
        raise ValueError(f"unsupported phase1 tenant: {tenant_key}")
    run = session.exec(select(OnboardingRunRecord).where(OnboardingRunRecord.idempotency_key == idempotency_key)).first()
    if run is None:
        run = OnboardingRunRecord(tenant_key=tenant_key, idempotency_key=idempotency_key, actor=actor)
        session.add(run)
        session.flush()
        for stage in OnboardingStage:
            session.add(OnboardingStageRecord(run_id=run.id, stage=stage.value))
    execute(session, run, providers or FakeProviderHub(), canary=canary)
    session.commit()
    session.refresh(run)
    return run


def retry(session: Session, run: OnboardingRunRecord, *, canary: ScopedCanary | None = None) -> OnboardingRunRecord:
    execute(session, run, FakeProviderHub(), canary=canary)
    session.commit()
    session.refresh(run)
    return run


def execute(session: Session, run: OnboardingRunRecord, providers: FakeProviderHub, *, canary: ScopedCanary | None = None) -> None:
    run.attempt_count += 1
    run.status = StageStatus.RUNNING.value
    stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all()
    stage_order = {stage.value: index for index, stage in enumerate(OnboardingStage)}
    stages.sort(key=lambda stage: stage_order[stage.stage])
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
        payload: dict[str, object] = {"tenant_key": run.tenant_key}
        if stage.stage == OnboardingStage.TENANT_DRAFTED.value:
            outcome = providers.provision_tenant(run.tenant_key)
        elif stage.stage == OnboardingStage.PRODUCTS_ASSIGNED.value:
            outcome = "UPDATED"
        elif stage.stage == OnboardingStage.NATIVE_INTEGRATION_VERIFIED.value:
            outcome, reconciliation = (canary or DeterministicScopedCanary()).verify(run.tenant_key)
            payload["reconciliation"] = reconciliation
            if outcome != "CANARY_OK":
                stage.status = StageStatus.FAILED.value
                stage.result_code = outcome
                stage.completed_at = _now()
                _record_evidence(session, run, stage, outcome, payload)
                # Do not destructively compensate prior successful stages. A retry reconciles
                # the desired manifest with observed state and resumes from this failed stage.
                run.status = StageStatus.FAILED.value
                run.updated_at = _now()
                return
        stage.status = StageStatus.SUCCEEDED.value
        stage.result_code = outcome
        stage.completed_at = _now()
        _record_evidence(session, run, stage, outcome, payload)
    run.status = StageStatus.SUCCEEDED.value
    run.updated_at = _now()


def _record_evidence(session: Session, run: OnboardingRunRecord, stage: OnboardingStageRecord, outcome: str, payload: dict[str, object]) -> None:
    digest = hashlib.sha256(f"{run.id}:{stage.stage}:{outcome}:{payload}".encode()).hexdigest()
    evidence = OnboardingEvidenceRecord(run_id=run.id, stage=stage.stage, result_code=outcome, digest=digest, payload=payload)
    duplicate = session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id, OnboardingEvidenceRecord.stage == stage.stage, OnboardingEvidenceRecord.digest == digest)).first()
    if duplicate is None:
        session.add(evidence)
