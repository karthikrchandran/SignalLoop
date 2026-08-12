"""Administrative and workload endpoints for bound eCRM installations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import select

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.core.config import settings
from app.domain.ecrm_installations.models import (
    DestinationReceipt,
    EcrmInstallationBinding,
    InstallationProjectionCheckpoint,
    InstallationRepairCandidate,
)
from app.domain.ecrm_installations.registry import ProvisionedInstallationRegistry
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.secrets import EnvSecretResolver
from app.domain.ecrm_installations.service import (
    ConflictingReplay,
    DestinationEnvelope,
    EcrmDestinationService,
    InstallationAuthError,
    SuspendedInstallation,
)

router = APIRouter(prefix="/ecrm-installations", tags=["ecrm-installations"])


class BindingPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_id: str = Field(min_length=1, max_length=128)
    secret_reference_id: str = Field(min_length=1, max_length=128)
    capabilities: list[str] = Field(min_length=1)
    status: str = Field(pattern="^(ACTIVE|SUSPENDED|DEGRADED)$")
    source_version: int = Field(ge=1)


class BindingPublic(BaseModel):
    workspace_id: str
    ecrm_cell_id: str
    ecrm_cell_key: str
    base_url: str
    capabilities: list[str]
    status: str
    verified_at: datetime | None
    rotated_at: datetime | None
    source_version: int


def _binding_public(row: EcrmInstallationBinding) -> BindingPublic:
    return BindingPublic.model_validate(row, from_attributes=True)


def _installation_registry() -> ProvisionedInstallationRegistry:
    return ProvisionedInstallationRegistry(
        settings.ECRM_INSTALLATION_ENDPOINTS,
        settings.ECRM_INSTALLATION_SECRET_REFERENCES,
    )


@router.put("/binding", response_model=BindingPublic, dependencies=[Depends(require_admin)])
def put_binding(*, session: SessionDep, workspace_id: WorkspaceIdDep, body: BindingPut) -> BindingPublic:
    repository = EcrmInstallationRepository(session)
    try:
        endpoint, secret_reference = _installation_registry().destination(
            body.endpoint_id, body.secret_reference_id
        )
        row = repository.save_binding(
            EcrmInstallationBinding(
                workspace_id=workspace_id,
                ecrm_cell_id=endpoint.ecrm_cell_id,
                ecrm_cell_key=endpoint.ecrm_cell_key,
                base_url=endpoint.base_url,
                credential_secret_ref=secret_reference.identifier,
                capabilities=body.capabilities,
                status=body.status,
                source_version=body.source_version,
            )
        )
    except (LookupError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    session.commit()
    return _binding_public(row)


@router.get("/binding", response_model=BindingPublic, dependencies=[Depends(require_admin)])
def get_binding(*, session: SessionDep, workspace_id: WorkspaceIdDep) -> BindingPublic:
    row = EcrmInstallationRepository(session).get_binding(workspace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Installation binding not found")
    return _binding_public(row)


@router.post("/deliveries", status_code=status.HTTP_202_ACCEPTED)
def receive_delivery(
    *,
    session: SessionDep,
    body: DestinationEnvelope,
    authorization: str = Header(alias="Authorization"),
    ecrm_cell_id: str = Header(alias="X-ECRM-Cell-Id"),
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> dict[str, object]:
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential:
        raise HTTPException(status_code=401, detail="Installation authentication failed")
    try:
        receipt = EcrmDestinationService(
            EcrmInstallationRepository(session),
            EnvSecretResolver(_installation_registry().environment_allowlist()),
        ).receive(
            ecrm_cell_id=ecrm_cell_id,
            credential=credential,
            idempotency_key=idempotency_key,
            envelope=body,
        )
        session.commit()
    except InstallationAuthError:
        session.rollback()
        raise HTTPException(status_code=401, detail="Installation authentication failed")
    except SuspendedInstallation:
        session.rollback()
        raise HTTPException(status_code=423, detail="Installation suspended")
    except ConflictingReplay:
        session.rollback()
        raise HTTPException(status_code=409, detail="Conflicting idempotency replay")
    return {
        "receipt_id": str(receipt.id),
        "workspace_id": receipt.workspace_id,
        "source_event_id": receipt.source_event_id,
        "source_version": receipt.source_version,
        "status": receipt.status,
    }


@router.get("/operations", dependencies=[Depends(require_admin)])
def operations(*, session: SessionDep, workspace_id: WorkspaceIdDep) -> dict[str, object]:
    receipts = session.exec(
        select(DestinationReceipt).where(DestinationReceipt.workspace_id == workspace_id)
    ).all()
    checkpoints = session.exec(
        select(InstallationProjectionCheckpoint).where(
            InstallationProjectionCheckpoint.workspace_id == workspace_id
        )
    ).all()
    repairs = session.exec(
        select(InstallationRepairCandidate).where(
            InstallationRepairCandidate.workspace_id == workspace_id
        )
    ).all()
    return {
        "receipts": [
            {
                "id": str(row.id), "event_kind": row.event_kind,
                "source_event_id": row.source_event_id, "source_version": row.source_version,
                "stream_key": row.stream_key, "status": row.status,
                "attempt_count": row.attempt_count, "last_error": row.last_error,
            }
            for row in receipts
        ],
        "checkpoints": [
            {"stream_key": row.stream_key, "source_version": row.source_version, "applied_count": row.applied_count, "state": row.state}
            for row in checkpoints
        ],
        "repairs": [
            {"id": str(row.id), "stream_key": row.stream_key, "status": row.status, "resolution": row.resolution}
            for row in repairs
        ],
    }


@router.post("/receipts/{receipt_id}/replay", dependencies=[Depends(require_admin)])
def replay(*, session: SessionDep, workspace_id: WorkspaceIdDep, receipt_id: UUID) -> dict[str, str]:
    try:
        receipt = EcrmInstallationRepository(session).replay_receipt(workspace_id, receipt_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Receipt not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    session.commit()
    return {"id": str(receipt.id), "status": receipt.status}


class ReconcileBody(BaseModel):
    stream_key: str = Field(min_length=1, max_length=255)
    source_count: int = Field(ge=0)
    source_checkpoint: int = Field(ge=0)


@router.post("/reconcile", dependencies=[Depends(require_admin)])
def reconcile(*, session: SessionDep, workspace_id: WorkspaceIdDep, body: ReconcileBody) -> dict[str, object]:
    repair = EcrmInstallationRepository(session).reconcile_stream(
        workspace_id=workspace_id, **body.model_dump()
    )
    session.commit()
    return {"matched": repair is None, "repair_id": str(repair.id) if repair else None}
