"""Tenant-safe repository for installation delivery and projection state."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.ecrm_installations.models import (
    DestinationReceipt,
    EcrmInstallationBinding,
    InstallationProjectionCheckpoint,
    InstallationRepairCandidate,
    RevenueOsInstallationProjection,
    utc_now,
)
from app.domain.tenants.models import ProductCode, Tenant, TenantEntitlement


def _canonical_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EcrmInstallationRepository:
    """All public lookups require workspace scope unless resolving authenticated cell identity."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save_binding(self, binding: EcrmInstallationBinding) -> EcrmInstallationBinding:
        if not binding.base_url.startswith("https://"):
            raise ValueError("eCRM base_url must use https")
        existing = self.session.get(EcrmInstallationBinding, binding.workspace_id)
        if existing is not None and existing is not binding:
            immutable_destination = (
                "ecrm_cell_id",
                "ecrm_cell_key",
                "base_url",
            )
            if any(
                getattr(existing, field) != getattr(binding, field)
                for field in immutable_destination
            ):
                raise ValueError("installation destination is immutable")
            secret_rotated = (
                existing.credential_secret_ref != binding.credential_secret_ref
            )
            if secret_rotated and (
                binding.rotated_at is None
                or binding.source_version != existing.source_version + 1
            ):
                raise ValueError(
                    "installation secret rotation requires the next source version"
                )
            if not secret_rotated and binding.source_version < existing.source_version:
                raise ValueError("installation source version cannot move backwards")
            if secret_rotated:
                existing.credential_secret_ref = binding.credential_secret_ref
            for field in (
                "capabilities", "status", "verified_at", "rotated_at", "source_version",
            ):
                setattr(existing, field, getattr(binding, field))
            existing.updated_at = utc_now()
            binding = existing
        self.session.add(binding)
        self.session.flush()
        append_audit_event_to_session(
            self.session,
            event_name="ecrm.installation.binding_saved",
            workspace_id=binding.workspace_id,
            resource_type="ecrm_installation_binding",
            resource_id=binding.ecrm_cell_id,
            payload={"status": binding.status, "source_version": binding.source_version},
        )
        return binding

    def get_binding(
        self, workspace_id: str, *, ecrm_cell_id: str | None = None
    ) -> EcrmInstallationBinding | None:
        clauses = [EcrmInstallationBinding.workspace_id == workspace_id]
        if ecrm_cell_id is not None:
            clauses.append(EcrmInstallationBinding.ecrm_cell_id == ecrm_cell_id)
        return self.session.exec(select(EcrmInstallationBinding).where(*clauses)).one_or_none()

    def get_binding_by_cell(self, ecrm_cell_id: str) -> EcrmInstallationBinding | None:
        return self.session.exec(
            select(EcrmInstallationBinding).where(EcrmInstallationBinding.ecrm_cell_id == ecrm_cell_id)
        ).one_or_none()

    def list_receipts(self, workspace_id: str) -> list[DestinationReceipt]:
        received_at = cast(Any, DestinationReceipt.received_at)
        return list(
            self.session.exec(
                select(DestinationReceipt)
                .where(DestinationReceipt.workspace_id == workspace_id)
                .order_by(received_at)
            ).all()
        )

    def claim_due_receipts(
        self,
        *,
        workspace_id: str | None = None,
        limit: int = 100,
        lease_seconds: int = 60,
        worker_id: str = "installation-projection-worker",
    ) -> list[DestinationReceipt]:
        now = utc_now()
        receipt_status = cast(Any, DestinationReceipt.status)
        next_attempt_at = cast(Any, DestinationReceipt.next_attempt_at)
        lease_expires_at = cast(Any, DestinationReceipt.lease_expires_at)
        received_at = cast(Any, DestinationReceipt.received_at)
        clauses = [
            or_(
                and_(
                    receipt_status.in_(("RECEIVED", "RETRY_SCHEDULED", "HELD_GAP")),
                    next_attempt_at.is_(None) | (next_attempt_at <= now),
                ),
                and_(
                    receipt_status == "IN_FLIGHT",
                    lease_expires_at.is_not(None),
                    lease_expires_at <= now,
                ),
            )
        ]
        if workspace_id is not None:
            receipt_workspace_id = cast(Any, DestinationReceipt.workspace_id)
            clauses.append(receipt_workspace_id == workspace_id)
        rows = list(
            self.session.exec(
                select(DestinationReceipt)
                .where(*clauses)
                .order_by(received_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
        )
        for row in rows:
            row.status = "IN_FLIGHT"
            row.lease_owner = worker_id
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.fence_token += 1
            row.updated_at = now
            self.session.add(row)
        self.session.commit()
        return rows

    def checkpoint(self, workspace_id: str, stream_key: str) -> InstallationProjectionCheckpoint | None:
        return self.session.exec(
            select(InstallationProjectionCheckpoint).where(
                InstallationProjectionCheckpoint.workspace_id == workspace_id,
                InstallationProjectionCheckpoint.stream_key == stream_key,
            )
        ).one_or_none()

    def get_revenueos_projection(self, workspace_id: str) -> RevenueOsInstallationProjection | None:
        tenant = self.session.exec(select(Tenant).where(Tenant.key == workspace_id)).one_or_none()
        if tenant is None:
            return None
        entitlement = self.session.exec(
            select(TenantEntitlement).where(
                TenantEntitlement.tenant_id == tenant.id,
                TenantEntitlement.product_code == ProductCode.REVENUE_OS,
                TenantEntitlement.status == "ACTIVE",
            )
        ).one_or_none()
        if entitlement is None:
            return None
        updated_at = cast(Any, RevenueOsInstallationProjection.updated_at)
        return self.session.exec(
            select(RevenueOsInstallationProjection)
            .where(RevenueOsInstallationProjection.workspace_id == workspace_id)
            .order_by(updated_at.desc())
        ).first()

    def replay_receipt(self, workspace_id: str, receipt_id: UUID) -> DestinationReceipt:
        receipt = self.session.get(DestinationReceipt, receipt_id)
        if receipt is None or receipt.workspace_id != workspace_id:
            raise KeyError("receipt not found")
        if receipt.status != "DEAD_LETTER":
            raise ValueError("only dead-letter receipts can be replayed")
        receipt.status = "RECEIVED"
        receipt.attempt_count = 0
        receipt.next_attempt_at = None
        receipt.dead_letter_at = None
        receipt.last_error = None
        receipt.replayed_at = utc_now()
        receipt.updated_at = utc_now()
        self.session.add(receipt)
        append_audit_event_to_session(
            self.session,
            event_name="ecrm.installation.receipt_replayed",
            workspace_id=workspace_id,
            resource_type="ecrm_destination_receipt",
            resource_id=str(receipt.id),
            payload={"source_event_id": receipt.source_event_id},
        )
        return receipt

    def reconcile_stream(
        self,
        *,
        workspace_id: str,
        stream_key: str,
        source_count: int,
        source_checkpoint: int,
    ) -> InstallationRepairCandidate | None:
        checkpoint = self.checkpoint(workspace_id, stream_key)
        local_count = checkpoint.applied_count if checkpoint else 0
        local_checkpoint = checkpoint.source_version if checkpoint else 0
        if (source_count, source_checkpoint) == (local_count, local_checkpoint):
            return None
        mismatch_hash = _canonical_hash(
            [source_count, source_checkpoint, local_count, local_checkpoint]
        )
        existing = self._repair_candidate(workspace_id, stream_key, mismatch_hash)
        if existing is not None:
            return existing
        repair = InstallationRepairCandidate(
            workspace_id=workspace_id,
            stream_key=stream_key,
            mismatch_hash=mismatch_hash,
            source_count=source_count,
            local_count=local_count,
            source_checkpoint=source_checkpoint,
            local_checkpoint=local_checkpoint,
        )
        self.session.add(repair)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            existing = self._repair_candidate(
                workspace_id, stream_key, mismatch_hash
            )
            if existing is None:
                raise
            return existing
        append_audit_event_to_session(
            self.session,
            event_name="ecrm.installation.repair_candidate_created",
            workspace_id=workspace_id,
            resource_type="ecrm_installation_repair_candidate",
            resource_id=str(repair.id),
            payload={
                "stream_key": stream_key,
                "source_count": source_count,
                "local_count": local_count,
                "source_checkpoint": source_checkpoint,
                "local_checkpoint": local_checkpoint,
            },
        )
        return repair

    def _repair_candidate(
        self, workspace_id: str, stream_key: str, mismatch_hash: str
    ) -> InstallationRepairCandidate | None:
        return self.session.exec(
            select(InstallationRepairCandidate).where(
                InstallationRepairCandidate.workspace_id == workspace_id,
                InstallationRepairCandidate.stream_key == stream_key,
                InstallationRepairCandidate.mismatch_hash == mismatch_hash,
            )
        ).one_or_none()

    def resolve_repair(
        self, workspace_id: str, repair_id: UUID, *, resolution: str
    ) -> InstallationRepairCandidate:
        repair = self.session.get(InstallationRepairCandidate, repair_id)
        if repair is None or repair.workspace_id != workspace_id:
            raise KeyError("repair candidate not found")
        repair.status = "RESOLVED"
        repair.resolution = resolution
        repair.resolved_at = utc_now()
        self.session.add(repair)
        append_audit_event_to_session(
            self.session,
            event_name="ecrm.installation.repair_candidate_resolved",
            workspace_id=workspace_id,
            resource_type="ecrm_installation_repair_candidate",
            resource_id=str(repair.id),
            payload={"resolution": resolution},
        )
        return repair
