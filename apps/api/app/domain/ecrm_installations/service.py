"""Authenticated destination ingestion and durable installation projection worker."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlmodel import select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.ecrm_installations.models import (
    DestinationReceipt,
    InstallationProjectionCheckpoint,
    RevenueOsInstallationProjection,
    utc_now,
)
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import SecretResolver


class InstallationAuthError(ValueError):
    pass


class SuspendedInstallation(ValueError):
    pass


class ConflictingReplay(ValueError):
    pass


class DestinationEnvelope(BaseModel):
    source_event_id: str = Field(min_length=1, max_length=255)
    source_version: int = Field(ge=1)
    stream_key: str = Field(min_length=1, max_length=255)
    event_kind: str = Field(pattern="^(SHARED_RECORD|WORKFLOW_EVENT)$")
    payload: dict[str, Any]


def _payload_hash(envelope: DestinationEnvelope) -> str:
    raw = json.dumps(envelope.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EcrmDestinationService:
    def __init__(self, repository: EcrmInstallationRepository, secrets: SecretResolver) -> None:
        self.repository = repository
        self.secrets = secrets

    def receive(
        self,
        *,
        ecrm_cell_id: str,
        credential: str,
        idempotency_key: str,
        envelope: DestinationEnvelope,
    ) -> DestinationReceipt:
        binding = self.repository.get_binding_by_cell(ecrm_cell_id)
        if binding is None:
            raise InstallationAuthError("installation authentication failed")
        try:
            expected = self.secrets.resolve(binding.credential_secret_ref)
        except (LookupError, ValueError) as exc:
            raise InstallationAuthError("installation authentication failed") from exc
        if not hmac.compare_digest(expected, credential):
            raise InstallationAuthError("installation authentication failed")
        if binding.status not in {"ACTIVE", "DEGRADED"}:
            raise SuspendedInstallation("installation is not active")
        if envelope.event_kind not in binding.capabilities:
            raise InstallationAuthError("installation capability denied")

        digest = _payload_hash(envelope)
        existing = self.repository.session.exec(
            select(DestinationReceipt).where(
                DestinationReceipt.workspace_id == binding.workspace_id,
                DestinationReceipt.idempotency_key == idempotency_key,
            )
        ).one_or_none()
        if existing is not None:
            if existing.payload_hash != digest:
                raise ConflictingReplay("idempotency key already has different content")
            return existing
        receipt = DestinationReceipt(
            workspace_id=binding.workspace_id,
            ecrm_cell_id=binding.ecrm_cell_id,
            source_event_id=envelope.source_event_id,
            source_version=envelope.source_version,
            stream_key=envelope.stream_key,
            event_kind=envelope.event_kind,
            idempotency_key=idempotency_key,
            payload_hash=digest,
            payload=envelope.payload,
        )
        self.repository.session.add(receipt)
        self.repository.session.flush()
        append_audit_event_to_session(
            self.repository.session,
            event_name="ecrm.installation.destination_received",
            workspace_id=binding.workspace_id,
            resource_type="ecrm_destination_receipt",
            resource_id=str(receipt.id),
            payload={
                "event_kind": envelope.event_kind,
                "source_event_id": envelope.source_event_id,
                "source_version": envelope.source_version,
                "stream_key": envelope.stream_key,
            },
        )
        return receipt


class InstallationProjectionWorker:
    def __init__(self, repository: EcrmInstallationRepository, *, max_attempts: int = 5) -> None:
        self.repository = repository
        self.max_attempts = max_attempts

    def run_once(self, *, workspace_id: str | None = None, limit: int = 100) -> dict[str, int]:
        result = {"applied": 0, "held": 0, "failed": 0}
        rows = self.repository.claim_due_receipts(workspace_id=workspace_id, limit=limit)
        for row in rows:
            try:
                settled = self.process(row.id)
            except Exception as exc:
                settled = self._record_failure(row, exc)
            if settled.status == "APPLIED":
                result["applied"] += 1
            elif settled.status == "HELD_GAP":
                result["held"] += 1
            elif settled.status in {"RETRY_SCHEDULED", "DEAD_LETTER"}:
                result["failed"] += 1
        return result

    def process(self, receipt_id: UUID, *, crash_after_side_effect: bool = False) -> DestinationReceipt:
        session = self.repository.session
        receipt = session.get(DestinationReceipt, receipt_id)
        if receipt is None:
            raise KeyError("receipt not found")
        binding = self.repository.get_binding(receipt.workspace_id, ecrm_cell_id=receipt.ecrm_cell_id)
        if binding is None or binding.status == "SUSPENDED":
            raise SuspendedInstallation("installation is not active")
        checkpoint = self.repository.checkpoint(receipt.workspace_id, receipt.stream_key)
        current_version = checkpoint.source_version if checkpoint else 0
        if receipt.source_version <= current_version:
            return self._settle(receipt, "APPLIED")
        if receipt.source_version > current_version + 1:
            receipt.status = "HELD_GAP"
            receipt.last_error = f"EXPECTED_VERSION_{current_version + 1}"
            receipt.lease_owner = None
            receipt.lease_expires_at = None
            receipt.next_attempt_at = utc_now() + timedelta(minutes=5)
            receipt.updated_at = utc_now()
            session.add(receipt)
            session.commit()
            return receipt
        if receipt.payload.get("force_error"):
            raise RuntimeError("forced projection error")

        projection = session.exec(
            select(RevenueOsInstallationProjection).where(
                RevenueOsInstallationProjection.workspace_id == receipt.workspace_id,
                RevenueOsInstallationProjection.stream_key == receipt.stream_key,
            )
        ).one_or_none()
        if projection is None:
            projection = RevenueOsInstallationProjection(
                workspace_id=receipt.workspace_id,
                ecrm_cell_id=receipt.ecrm_cell_id,
                stream_key=receipt.stream_key,
                source_event_id=receipt.source_event_id,
                source_version=receipt.source_version,
                payload_hash=receipt.payload_hash,
                projection=receipt.payload,
            )
        elif receipt.source_version > projection.source_version:
            projection.source_event_id = receipt.source_event_id
            projection.source_version = receipt.source_version
            projection.payload_hash = receipt.payload_hash
            projection.projection = receipt.payload
            projection.updated_at = utc_now()
        session.add(projection)
        session.commit()  # Side effect is durable before receipt acknowledgement.
        if crash_after_side_effect:
            raise RuntimeError("simulated crash")

        if checkpoint is None:
            checkpoint = InstallationProjectionCheckpoint(
                workspace_id=receipt.workspace_id,
                ecrm_cell_id=receipt.ecrm_cell_id,
                stream_key=receipt.stream_key,
            )
        checkpoint.source_event_id = receipt.source_event_id
        checkpoint.source_version = receipt.source_version
        checkpoint.applied_count += 1
        checkpoint.state = "CURRENT"
        checkpoint.updated_at = utc_now()
        session.add(checkpoint)
        append_audit_event_to_session(
            session,
            event_name="ecrm.installation.projection_applied",
            workspace_id=receipt.workspace_id,
            resource_type="revenueos_installation_projection",
            resource_id=str(projection.id),
            payload={
                "stream_key": receipt.stream_key,
                "source_event_id": receipt.source_event_id,
                "source_version": receipt.source_version,
            },
        )
        return self._settle(receipt, "APPLIED")

    def _settle(self, receipt: DestinationReceipt, status: str) -> DestinationReceipt:
        receipt.status = status
        receipt.last_error = None
        receipt.next_attempt_at = None
        receipt.lease_owner = None
        receipt.lease_expires_at = None
        receipt.updated_at = utc_now()
        self.repository.session.add(receipt)
        self.repository.session.commit()
        return receipt

    def _record_failure(self, receipt: DestinationReceipt, error: Exception) -> DestinationReceipt:
        receipt.attempt_count += 1
        receipt.last_error = type(error).__name__
        receipt.lease_owner = None
        receipt.lease_expires_at = None
        receipt.updated_at = utc_now()
        if receipt.attempt_count >= self.max_attempts:
            receipt.status = "DEAD_LETTER"
            receipt.dead_letter_at = utc_now()
            receipt.next_attempt_at = None
            event_name = "ecrm.installation.projection_dead_lettered"
        else:
            receipt.status = "RETRY_SCHEDULED"
            receipt.next_attempt_at = utc_now() + timedelta(seconds=min(300, 10 * (2 ** (receipt.attempt_count - 1))))
            event_name = "ecrm.installation.projection_retry_scheduled"
        self.repository.session.add(receipt)
        append_audit_event_to_session(
            self.repository.session,
            event_name=event_name,
            workspace_id=receipt.workspace_id,
            resource_type="ecrm_destination_receipt",
            resource_id=str(receipt.id),
            payload={"attempt_count": receipt.attempt_count, "error_code": receipt.last_error},
        )
        self.repository.session.commit()
        return receipt
