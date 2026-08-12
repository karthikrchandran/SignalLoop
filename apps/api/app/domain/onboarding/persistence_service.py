from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlmodel import Session, select

from .evidence import EvidenceBundle, EvidenceRecord, redact_payload
from .manifest import load_phase1_manifests
from .models import OnboardingStage, StageStatus
from .persistence import (
    OnboardingEvidenceBundleRecord,
    OnboardingEvidenceRecord,
    OnboardingRunRecord,
    OnboardingStageRecord,
)
from .providers import FakeProviderHub


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


_LEASE_DURATION = timedelta(minutes=5)


def _input_hash(input_payload: dict[str, object] | None) -> str:
    canonical = json.dumps(redact_payload(input_payload or {}), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


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
    desired_version: str = "phase1",
    input_payload: dict[str, object] | None = None,
    evidence_signer: Ed25519PrivateKey | None = None,
) -> OnboardingRunRecord:
    if tenant_key not in load_phase1_manifests():
        raise ValueError(f"unsupported phase1 tenant: {tenant_key}")
    input_hash = _input_hash(input_payload)
    run = session.exec(select(OnboardingRunRecord).where(
        OnboardingRunRecord.tenant_key == tenant_key,
        OnboardingRunRecord.desired_version == desired_version,
        OnboardingRunRecord.idempotency_key == idempotency_key,
        OnboardingRunRecord.input_hash == input_hash,
    )).first()
    if run is None:
        run = OnboardingRunRecord(tenant_key=tenant_key, idempotency_key=idempotency_key, desired_version=desired_version, input_hash=input_hash, actor=actor)
        session.add(run)
        session.flush()
        for stage in OnboardingStage:
            session.add(OnboardingStageRecord(run_id=run.id, stage=stage.value))
    execute(session, run, providers or FakeProviderHub(), canary=canary, evidence_signer=evidence_signer)
    session.commit()
    session.refresh(run)
    return run


def retry(session: Session, run: OnboardingRunRecord, *, canary: ScopedCanary | None = None, evidence_signer: Ed25519PrivateKey | None = None) -> OnboardingRunRecord:
    execute(session, run, FakeProviderHub(), canary=canary, evidence_signer=evidence_signer)
    session.commit()
    session.refresh(run)
    return run


def execute(session: Session, run: OnboardingRunRecord, providers: FakeProviderHub, *, canary: ScopedCanary | None = None, evidence_signer: Ed25519PrivateKey | None = None) -> None:
    recover_expired(session, run)
    run.attempt_count += 1
    run.status = StageStatus.RUNNING.value
    run.lease_expires_at = _now() + _LEASE_DURATION
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
        stage.started_at = _now()
        stage.lease_expires_at = _now() + _LEASE_DURATION
        outcome = "UNCHANGED"
        payload: dict[str, object] = {"tenant_key": run.tenant_key}
        try:
            if stage.stage == OnboardingStage.TENANT_DRAFTED.value:
                outcome = providers.provision_tenant(run.tenant_key)
            elif stage.stage == OnboardingStage.PRODUCTS_ASSIGNED.value:
                outcome = "UPDATED"
            elif stage.stage == OnboardingStage.NATIVE_INTEGRATION_VERIFIED.value:
                outcome, reconciliation = (canary or DeterministicScopedCanary()).verify(run.tenant_key)
                payload["reconciliation"] = reconciliation
                if outcome != "CANARY_OK":
                    _fail_stage(session, run, stage, outcome, payload)
                    return
        except Exception:
            _fail_stage(session, run, stage, "PROVIDER_EXCEPTION", payload)
            return
        stage.status = StageStatus.SUCCEEDED.value
        stage.result_code = outcome
        stage.completed_at = _now()
        stage.lease_expires_at = None
        _record_evidence(session, run, stage, outcome, payload)
    run.status = StageStatus.SUCCEEDED.value
    run.updated_at = _now()
    run.lease_expires_at = None
    _persist_bundle(session, run, evidence_signer or Ed25519PrivateKey.generate())


def recover_expired(session: Session, run: OnboardingRunRecord) -> None:
    """Recover abandoned leased work without deleting any prior provisioned resource."""
    now = _now()
    stages = session.exec(select(OnboardingStageRecord).where(OnboardingStageRecord.run_id == run.id)).all()
    for stage in stages:
        if stage.status == StageStatus.RUNNING.value and stage.lease_expires_at and _as_utc(stage.lease_expires_at) <= now:
            stage.status = StageStatus.FAILED.value
            stage.result_code = "LEASE_EXPIRED_RECONCILE_REQUIRED"
            stage.completed_at = now
            stage.lease_expires_at = None
            _record_evidence(session, run, stage, stage.result_code, {"tenant_key": run.tenant_key, "compensation": "NONE_RECONCILE_ON_RETRY"})
    if run.status == StageStatus.RUNNING.value and run.lease_expires_at and _as_utc(run.lease_expires_at) <= now:
        run.status = StageStatus.FAILED.value
        run.lease_expires_at = None


def _record_evidence(session: Session, run: OnboardingRunRecord, stage: OnboardingStageRecord, outcome: str, payload: dict[str, object]) -> None:
    safe_payload = redact_payload(payload)
    digest = hashlib.sha256(f"{run.id}:{stage.stage}:{outcome}:{safe_payload}".encode()).hexdigest()
    evidence = OnboardingEvidenceRecord(run_id=run.id, stage=stage.stage, result_code=outcome, digest=digest, payload=safe_payload)
    duplicate = session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id, OnboardingEvidenceRecord.stage == stage.stage, OnboardingEvidenceRecord.digest == digest)).first()
    if duplicate is None:
        session.add(evidence)


def _fail_stage(session: Session, run: OnboardingRunRecord, stage: OnboardingStageRecord, outcome: str, payload: dict[str, object]) -> None:
    stage.status = StageStatus.FAILED.value
    stage.result_code = outcome
    stage.completed_at = _now()
    stage.lease_expires_at = None
    _record_evidence(session, run, stage, outcome, payload)
    # Safe compensation posture: never delete existing tenant resources; retry reconciles them.
    run.status = StageStatus.FAILED.value
    run.updated_at = _now()
    run.lease_expires_at = None


def _persist_bundle(session: Session, run: OnboardingRunRecord, signer: Ed25519PrivateKey) -> None:
    evidence = session.exec(select(OnboardingEvidenceRecord).where(OnboardingEvidenceRecord.run_id == run.id)).all()
    records = tuple(EvidenceRecord(str(run.id), item.stage, item.result_code, json.dumps(redact_payload(item.payload), sort_keys=True, separators=(",", ":")), item.digest) for item in evidence)
    bundle = EvidenceBundle.from_records(run.tenant_key, records, signer)
    digest = hashlib.sha256(bundle.canonical_payload.encode()).hexdigest()
    exists = session.exec(select(OnboardingEvidenceBundleRecord).where(OnboardingEvidenceBundleRecord.run_id == run.id, OnboardingEvidenceBundleRecord.digest == digest)).first()
    if exists is None:
        session.add(OnboardingEvidenceBundleRecord(run_id=run.id, digest=digest, canonical_payload=bundle.canonical_payload, public_key=bundle.public_key, signature=bundle.signature))
