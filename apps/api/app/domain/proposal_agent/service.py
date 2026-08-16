"""Lease-safe orchestration, reconciliation, and DLQ controls for proposals."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import update
from sqlmodel import Session, select

from app.core.encryption import decrypt, encrypt
from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.commercial_agents.capacity import (
    finalize_capacity,
    mark_capacity_unknown,
    reconcile_unknown_capacity,
    reserve_capacity,
)
from app.domain.commercial_agents.models import (
    AgentDeployment,
    AgentDeploymentStatus,
    AgentType,
)
from app.domain.ecrm_installations.models import EcrmInstallationBinding
from app.domain.proposal_agent.ecrm_adapter import (
    EcrmProposalAdapter,
    EcrmProposalCommand,
    EcrmProposalReceipt,
)
from app.domain.proposal_agent.models import (
    ProposalGenerationEvidence,
    ProposalGenerationJob,
    ProposalGenerationReceipt,
    ProposalJobStatus,
)


class ProposalAgentError(ValueError):
    """Deterministic proposal orchestration error."""


class ProposalLeaseLost(ProposalAgentError):
    """The worker no longer owns the proposal finalization lease."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _digest(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def enqueue_proposal_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    deployment_id: uuid.UUID,
    ecrm_cell_id: str,
    client_account_id: str,
    proposal_id: str,
    mode: str,
    command_key: str,
    input_digest: str,
    source_digest: str,
    request_payload: dict[str, Any],
    max_attempts: int = 5,
    now: datetime | None = None,
) -> ProposalGenerationJob:
    values = (ecrm_cell_id, client_account_id, proposal_id, command_key)
    if any(not value.strip() for value in values) or mode not in {
        "TEMPLATE",
        "GENERATIVE",
    }:
        raise ProposalAgentError(
            "cell, client, proposal, command key, and supported mode are required"
        )
    if any(len(value) != 64 for value in (input_digest, source_digest)):
        raise ProposalAgentError("input and source digests must be SHA-256 values")
    existing = session.exec(
        select(ProposalGenerationJob).where(
            ProposalGenerationJob.tenant_id == tenant_id,
            ProposalGenerationJob.workspace_id == workspace_id,
            ProposalGenerationJob.command_key == command_key.strip(),
        )
    ).one_or_none()
    if existing is not None:
        if (
            existing.deployment_id != deployment_id
            or existing.ecrm_cell_id != ecrm_cell_id
            or existing.client_account_id != client_account_id
            or existing.proposal_id != proposal_id
            or existing.input_digest != input_digest
            or existing.source_digest != source_digest
        ):
            raise ProposalAgentError(
                "proposal command key conflicts with stored request"
            )
        return existing
    deployment = session.get(AgentDeployment, deployment_id)
    binding = session.get(EcrmInstallationBinding, workspace_id)
    if (
        deployment is None
        or deployment.tenant_id != tenant_id
        or deployment.workspace_id != workspace_id
        or deployment.agent_type != AgentType.PROPOSAL_DRAFTING
        or deployment.status != AgentDeploymentStatus.ACTIVE
        or binding is None
        or binding.status != "ACTIVE"
        or binding.ecrm_cell_id != ecrm_cell_id
        or not {"proposal.version.create", "proposal.receipt.lookup"}.issubset(
            binding.capabilities
        )
    ):
        raise ProposalAgentError(
            "active owned Proposal Agent and exact eCRM cell binding are required"
        )
    at = _utc(now or datetime.now(timezone.utc))
    encrypted_request = encrypt(
        json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    )
    job = ProposalGenerationJob(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        deployment_id=deployment_id,
        ecrm_cell_id=ecrm_cell_id,
        client_account_id=client_account_id,
        proposal_id=proposal_id,
        mode=mode,
        command_key=command_key.strip(),
        input_digest=input_digest.lower(),
        source_digest=source_digest.lower(),
        encrypted_request=encrypted_request,
        max_attempts=max_attempts,
        available_at=at,
        created_at=at,
        updated_at=at,
    )
    session.add(job)
    session.flush()
    session.add(
        ProposalGenerationEvidence(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            job_id=job.id,
            source_type="ECRM_APPROVED_SOURCE_MANIFEST",
            source_reference=f"proposal:{proposal_id}:sources",
            source_digest=source_digest.lower(),
            retrieved_at=at,
        )
    )
    session.flush()
    return job


def _claim(
    session: Session, *, now: datetime, lease_seconds: int = 300
) -> ProposalGenerationJob | None:
    candidate = session.exec(
        select(ProposalGenerationJob.id)
        .where(
            ProposalGenerationJob.status.in_(
                [
                    ProposalJobStatus.PENDING.value,
                    ProposalJobStatus.RETRY_SCHEDULED.value,
                ]
            ),
            ProposalGenerationJob.available_at <= now,
        )
        .order_by(ProposalGenerationJob.created_at, ProposalGenerationJob.id)
        .limit(1)
    ).first()
    if candidate is None:
        return None
    token = uuid.uuid4()
    result = session.exec(
        update(ProposalGenerationJob)
        .where(
            ProposalGenerationJob.id == candidate,
            ProposalGenerationJob.status.in_(
                [
                    ProposalJobStatus.PENDING.value,
                    ProposalJobStatus.RETRY_SCHEDULED.value,
                ]
            ),
            ProposalGenerationJob.available_at <= now,
        )
        .values(
            status=ProposalJobStatus.IN_PROGRESS.value,
            attempt_count=ProposalGenerationJob.attempt_count + 1,
            lease_token=token,
            lease_expires_at=now + timedelta(seconds=lease_seconds),
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    return session.exec(
        select(ProposalGenerationJob).where(
            ProposalGenerationJob.id == candidate,
            ProposalGenerationJob.lease_token == token,
        )
    ).one()


def _command(job: ProposalGenerationJob) -> EcrmProposalCommand:
    payload = json.loads(decrypt(job.encrypted_request))
    if not isinstance(payload, dict):
        raise ProposalAgentError("decrypted proposal request must be an object")
    return EcrmProposalCommand(
        command_key=job.command_key,
        ecrm_cell_id=job.ecrm_cell_id,
        client_account_id=job.client_account_id,
        proposal_id=job.proposal_id,
        mode=job.mode,
        payload_digest=job.input_digest,
        source_digest=job.source_digest,
        payload=payload,
    )


def _validate_receipt(job: ProposalGenerationJob, receipt: EcrmProposalReceipt) -> None:
    if (
        receipt.command_key != job.command_key
        or receipt.ecrm_cell_id != job.ecrm_cell_id
        or receipt.client_account_id != job.client_account_id
        or receipt.proposal_id != job.proposal_id
        or receipt.content_digest != job.input_digest
    ):
        raise ProposalAgentError(
            "eCRM proposal receipt does not match the durable command"
        )


def _persist_success(
    session: Session,
    *,
    job: ProposalGenerationJob,
    receipt: EcrmProposalReceipt,
    now: datetime,
    reconcile: bool = False,
    actor_id: uuid.UUID | None = None,
    actor_role: str | None = None,
) -> ProposalGenerationJob:
    _validate_receipt(job, receipt)
    if job.usage_reservation_id is None:
        raise ProposalAgentError("proposal capacity reservation is missing")
    if not reconcile:
        lease_token = job.lease_token
        if lease_token is None:
            raise ProposalLeaseLost("proposal completion lease is missing")
        claimed = session.exec(
            update(ProposalGenerationJob)
            .where(
                ProposalGenerationJob.id == job.id,
                ProposalGenerationJob.status == ProposalJobStatus.IN_PROGRESS.value,
                ProposalGenerationJob.lease_token == lease_token,
                ProposalGenerationJob.lease_expires_at >= now,
            )
            .values(
                status=ProposalJobStatus.COMPLETED.value,
                completed_at=now,
                lease_token=None,
                lease_expires_at=None,
                last_error_code=None,
                last_error_detail=None,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            session.rollback()
            current = session.get(ProposalGenerationJob, job.id)
            if (
                current is not None
                and current.status == ProposalJobStatus.IN_PROGRESS
                and current.lease_token == lease_token
                and current.usage_reservation_id is not None
            ):
                mark_capacity_unknown(
                    session,
                    reservation_id=current.usage_reservation_id,
                    reason="PROPOSAL_COMPLETION_LEASE_LOST",
                    now=now,
                )
                current.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
                current.lease_token = None
                current.lease_expires_at = None
                current.last_error_code = "PROPOSAL_COMPLETION_LEASE_LOST"
                current.updated_at = now
                session.add(current)
                session.commit()
            raise ProposalLeaseLost("proposal completion lease is no longer owned")
    if reconcile:
        reconcile_unknown_capacity(
            session,
            reservation_id=job.usage_reservation_id,
            accepted=True,
            provider_receipt_id=receipt.receipt_id,
            actor_id=actor_id or uuid.UUID(int=0),
            actor_role=actor_role or "reconciler",
            reason="eCRM proposal receipt reconciled",
            now=now,
        )
    else:
        finalize_capacity(
            session,
            reservation_id=job.usage_reservation_id,
            provider_receipt_id=receipt.receipt_id,
            finalized_units=1,
            provider_units={"proposal_versions": 1},
            now=now,
        )
    session.add(
        ProposalGenerationReceipt(
            tenant_id=job.tenant_id,
            workspace_id=job.workspace_id,
            job_id=job.id,
            command_key=job.command_key,
            ecrm_receipt_id=receipt.receipt_id,
            ecrm_cell_id=receipt.ecrm_cell_id,
            client_account_id=receipt.client_account_id,
            proposal_id=receipt.proposal_id,
            version_id=receipt.version_id,
            version_number=receipt.version_number,
            content_digest=receipt.content_digest,
            artifact_digest=receipt.artifact_digest,
            finalized_at=now,
        )
    )
    if reconcile:
        job.status = ProposalJobStatus.COMPLETED
        job.completed_at = now
        job.lease_token = None
        job.lease_expires_at = None
        job.last_error_code = None
        job.last_error_detail = None
        job.updated_at = now
        session.add(job)
    append_audit_event_to_session(
        session,
        event_name="proposal_agent.version.completed"
        if not reconcile
        else "proposal_agent.version.reconciled",
        workspace_id=job.workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="proposal_generation_job",
        resource_id=str(job.id),
        payload={
            "proposal_id": job.proposal_id,
            "version_id": receipt.version_id,
            "version_number": receipt.version_number,
        },
    )
    session.flush()
    return job


def _record_preinvoke_failure(
    session: Session, job: ProposalGenerationJob, error: Exception, now: datetime
) -> None:
    terminal = job.attempt_count >= job.max_attempts
    job.status = (
        ProposalJobStatus.DEAD_LETTER if terminal else ProposalJobStatus.RETRY_SCHEDULED
    )
    job.available_at = now + timedelta(
        minutes=min(60, 2 ** max(0, job.attempt_count - 1))
    )
    job.lease_token = None
    job.lease_expires_at = None
    job.last_error_code = type(error).__name__[:64]
    job.last_error_detail = str(error)[:1000]
    job.updated_at = now
    session.add(job)
    session.commit()


def run_proposal_batch(
    session: Session,
    *,
    adapter: EcrmProposalAdapter,
    limit: int = 25,
) -> int:
    processed = 0
    for _ in range(limit):
        job = _claim(session, now=datetime.now(timezone.utc))
        if job is None:
            break
        try:
            command = _command(job)
            reservation = reserve_capacity(
                session,
                tenant_id=job.tenant_id,
                workspace_id=job.workspace_id,
                deployment_id=job.deployment_id,
                capacity_metric="proposal_version",
                idempotency_key=f"proposal-generation:{job.id}:{job.attempt_count}",
            )
            envelope = command.model_dump(mode="json", exclude={"payload"})
            job.command_envelope = envelope
            job.command_digest = _digest(envelope)
            job.usage_reservation_id = reservation.id
            job.command_attempted_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
        except Exception as exc:
            session.rollback()
            job = session.get(ProposalGenerationJob, job.id)
            if job is not None:
                _record_preinvoke_failure(session, job, exc, datetime.now(timezone.utc))
            processed += 1
            continue
        try:
            receipt = adapter.apply(command)
        except Exception as exc:
            session.rollback()
            job = session.get(ProposalGenerationJob, job.id)
            if job is not None and job.usage_reservation_id is not None:
                mark_capacity_unknown(
                    session,
                    reservation_id=job.usage_reservation_id,
                    reason=f"AMBIGUOUS_ECRM_OUTCOME:{type(exc).__name__}",
                )
                job.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
                job.lease_token = None
                job.lease_expires_at = None
                job.last_error_code = type(exc).__name__[:64]
                job.last_error_detail = str(exc)[:1000]
                job.updated_at = datetime.now(timezone.utc)
                session.add(job)
                session.commit()
            processed += 1
            continue
        completed_at = datetime.now(timezone.utc)
        session.refresh(job)
        lease_expires = _utc(job.lease_expires_at) if job.lease_expires_at else None
        if lease_expires is None or lease_expires < completed_at:
            mark_capacity_unknown(
                session,
                reservation_id=job.usage_reservation_id,
                reason="PROPOSAL_LEASE_EXPIRED_AFTER_ECRM_CALL",
            )
            job.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
            job.lease_token = None
            job.lease_expires_at = None
            session.add(job)
            session.commit()
        else:
            try:
                _persist_success(session, job=job, receipt=receipt, now=completed_at)
                session.commit()
            except ProposalAgentError as exc:
                session.rollback()
                job = session.get(ProposalGenerationJob, job.id)
                if job is not None and job.usage_reservation_id is not None:
                    mark_capacity_unknown(
                        session,
                        reservation_id=job.usage_reservation_id,
                        reason=f"INVALID_ECRM_RECEIPT:{type(exc).__name__}",
                    )
                    job.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
                    job.lease_token = None
                    job.lease_expires_at = None
                    job.last_error_code = type(exc).__name__[:64]
                    job.last_error_detail = str(exc)[:1000]
                    session.add(job)
                    session.commit()
        processed += 1
    return processed


def recover_expired_proposal_leases(
    session: Session, *, now: datetime | None = None
) -> int:
    at = _utc(now or datetime.now(timezone.utc))
    jobs = session.exec(
        select(ProposalGenerationJob).where(
            ProposalGenerationJob.status == ProposalJobStatus.IN_PROGRESS.value,
            ProposalGenerationJob.lease_expires_at < at,
        )
    ).all()
    for job in jobs:
        if job.command_attempted_at is not None:
            if job.usage_reservation_id is not None:
                mark_capacity_unknown(
                    session,
                    reservation_id=job.usage_reservation_id,
                    reason="PROPOSAL_WORKER_LEASE_EXPIRED_AFTER_COMMAND",
                    now=at,
                )
            job.status = ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME
        else:
            job.status = ProposalJobStatus.RETRY_SCHEDULED
            job.available_at = at
        job.lease_token = None
        job.lease_expires_at = None
        job.updated_at = at
        session.add(job)
    session.flush()
    return len(jobs)


def reconcile_unknown_proposal_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    job_id: uuid.UUID,
    adapter: EcrmProposalAdapter,
    accepted: bool = True,
    evidence_receipt_id: str | None = None,
    reason: str = "eCRM proposal receipt reconciled",
    actor_id: uuid.UUID,
    actor_role: str,
    capabilities: set[str],
) -> ProposalGenerationJob:
    if "agents.admin.manage" not in capabilities:
        raise ProposalAgentError("agent administration capability is required")
    job = session.exec(
        select(ProposalGenerationJob)
        .where(
            ProposalGenerationJob.id == job_id,
            ProposalGenerationJob.tenant_id == tenant_id,
            ProposalGenerationJob.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if job is None or job.status != ProposalJobStatus.UNKNOWN_EXTERNAL_OUTCOME:
        raise ProposalAgentError("unknown proposal job was not found")
    if not reason.strip():
        raise ProposalAgentError("reconciliation reason is required")
    receipt = adapter.lookup_receipt(job.command_key)
    if not accepted:
        if receipt is not None:
            raise ProposalAgentError("eCRM returned a receipt; reconcile as accepted")
        if not evidence_receipt_id or not evidence_receipt_id.strip():
            raise ProposalAgentError("provider absence evidence receipt is required")
        if job.usage_reservation_id is None:
            raise ProposalAgentError("proposal capacity reservation is missing")
        reconcile_unknown_capacity(
            session,
            reservation_id=job.usage_reservation_id,
            accepted=False,
            provider_receipt_id=evidence_receipt_id,
            actor_id=actor_id,
            actor_role=actor_role,
            reason=reason,
        )
        job.status = ProposalJobStatus.RETRY_SCHEDULED
        job.available_at = datetime.now(timezone.utc)
        job.command_attempted_at = None
        job.usage_reservation_id = None
        job.last_error_code = None
        job.last_error_detail = None
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        append_audit_event_to_session(
            session,
            event_name="proposal_agent.version.absence_reconciled",
            workspace_id=workspace_id,
            actor_id=actor_id,
            actor_role=actor_role,
            resource_type="proposal_generation_job",
            resource_id=str(job.id),
            payload={
                "evidence_receipt_id": evidence_receipt_id,
                "reason": reason,
                "tenant_id": str(tenant_id),
            },
        )
        session.flush()
        return job
    if receipt is None:
        raise ProposalAgentError("eCRM receipt is still unavailable; do not replay")
    return _persist_success(
        session,
        job=job,
        receipt=receipt,
        now=datetime.now(timezone.utc),
        reconcile=True,
        actor_id=actor_id,
        actor_role=actor_role,
    )


def replay_dead_letter_proposal_job(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    workspace_id: str,
    job_id: uuid.UUID,
    actor_id: uuid.UUID,
    actor_role: str,
    capabilities: set[str],
    reason: str,
) -> ProposalGenerationJob:
    if "agents.admin.manage" not in capabilities or not reason.strip():
        raise ProposalAgentError("agent administration and replay reason are required")
    job = session.exec(
        select(ProposalGenerationJob)
        .where(
            ProposalGenerationJob.id == job_id,
            ProposalGenerationJob.tenant_id == tenant_id,
            ProposalGenerationJob.workspace_id == workspace_id,
        )
        .with_for_update()
    ).one_or_none()
    if job is None or job.status != ProposalJobStatus.DEAD_LETTER:
        raise ProposalAgentError("dead-letter proposal job was not found")
    job.status = ProposalJobStatus.PENDING
    job.attempt_count = 0
    job.available_at = datetime.now(timezone.utc)
    job.last_error_code = None
    job.last_error_detail = None
    session.add(job)
    append_audit_event_to_session(
        session,
        event_name="proposal_agent.dead_letter.replayed",
        workspace_id=workspace_id,
        actor_id=actor_id,
        actor_role=actor_role,
        resource_type="proposal_generation_job",
        resource_id=str(job.id),
        payload={"reason": reason.strip(), "tenant_id": str(tenant_id)},
    )
    session.flush()
    return job
