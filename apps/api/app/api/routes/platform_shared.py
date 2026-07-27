from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.shared_records import service as shared_record_service

router = APIRouter(prefix="/platform-shared", tags=["platform-shared"])


@router.post("/imports/ecrm", dependencies=[Depends(require_admin)])
def import_from_ecrm(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    dry_run: bool = True,
) -> dict[str, object]:
    return {
        "summary": shared_record_service.import_from_ecrm(
            session=session,
            workspace_id=workspace_id,
            dry_run=dry_run,
        )
    }


@router.get("/reconciliation", dependencies=[Depends(require_admin)])
def get_reconciliation(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
) -> dict[str, object]:
    return shared_record_service.reconcile_with_ecrm(
        session=session,
        workspace_id=workspace_id,
    )
