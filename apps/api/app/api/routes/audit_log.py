"""Audit log query and export API for Story 5.2."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_admin
from app.api.request_context import WorkspaceIdDep
from app.domain.audit.audit_events import AuditEvent
from app.domain_models import AuditEventPublic, AuditEventsPage

router = APIRouter(prefix="/audit-log", tags=["audit-log"])

# ---------------------------------------------------------------------------
# In-process export job registry (MVP – single-process only)
# ---------------------------------------------------------------------------
_export_jobs: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# GET /audit-log
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=AuditEventsPage,
    dependencies=[Depends(require_admin)],
)
def list_audit_events(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    actor_id: Annotated[uuid.UUID | None, Query()] = None,
    action_type: Annotated[str | None, Query()] = None,
    from_date: Annotated[datetime | None, Query()] = None,
    to_date: Annotated[datetime | None, Query()] = None,
    correlation_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> AuditEventsPage:
    filters = [AuditEvent.workspace_id == workspace_id]
    if actor_id is not None:
        filters.append(AuditEvent.actor_id == actor_id)
    if action_type is not None:
        filters.append(AuditEvent.event_name == action_type)
    if from_date is not None:
        filters.append(AuditEvent.created_at >= from_date)
    if to_date is not None:
        filters.append(AuditEvent.created_at <= to_date)
    if correlation_id is not None:
        filters.append(AuditEvent.correlation_id == correlation_id)

    where_clause = and_(*filters)

    total: int = session.scalar(  # type: ignore[assignment]
        select(func.count()).select_from(AuditEvent).where(where_clause)
    ) or 0

    events = session.exec(
        select(AuditEvent)
        .where(where_clause)
        .order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()

    return AuditEventsPage(
        total=total,
        page=page,
        limit=limit,
        items=[
            AuditEventPublic(
                id=e.id,
                event_name=e.event_name,
                workspace_id=e.workspace_id,
                actor_id=e.actor_id,
                actor_role=e.actor_role,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                correlation_id=e.correlation_id,
                payload=e.payload,
                created_at=e.created_at,
            )
            for e in events
        ],
    )


# ---------------------------------------------------------------------------
# POST /audit-log/export — kick off an export job
# ---------------------------------------------------------------------------
@router.post(
    "/export",
    dependencies=[Depends(require_admin)],
)
def create_export_job(
    *,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    format: Annotated[str, Body(pattern="^(json|csv)$", embed=True)] = "json",
    from_date: Annotated[datetime | None, Body(embed=True)] = None,
    to_date: Annotated[datetime | None, Body(embed=True)] = None,
) -> dict[str, str]:
    job_id = str(uuid.uuid4())
    filters = [AuditEvent.workspace_id == workspace_id]
    if from_date is not None:
        filters.append(AuditEvent.created_at >= from_date)
    if to_date is not None:
        filters.append(AuditEvent.created_at <= to_date)

    events = session.exec(
        select(AuditEvent)
        .where(and_(*filters))
        .order_by(AuditEvent.created_at.desc())
    ).all()

    rows = [
        {
            "id": str(e.id),
            "event_name": e.event_name,
            "workspace_id": e.workspace_id,
            "actor_id": str(e.actor_id) if e.actor_id else None,
            "actor_role": e.actor_role,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "correlation_id": e.correlation_id,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]

    _export_jobs[job_id] = {
        "status": "complete",
        "format": format,
        "rows": rows,
        "workspace_id": workspace_id,
        "actor_id": str(current_user.id),
    }

    return {"job_id": job_id, "status": "complete"}


# ---------------------------------------------------------------------------
# GET /audit-log/export/{job_id} — download export
# ---------------------------------------------------------------------------
@router.get(
    "/export/{job_id}",
    dependencies=[Depends(require_admin)],
)
def download_export(
    *,
    job_id: str,
    workspace_id: WorkspaceIdDep,
) -> StreamingResponse:
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job["workspace_id"] != workspace_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    rows: list[dict[str, Any]] = job["rows"]
    fmt: str = job["format"]

    if fmt == "csv":
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                # flatten payload to string for CSV
                writer.writerow({**row, "payload": json.dumps(row["payload"])})
        buf.seek(0)
        return StreamingResponse(
            iter([buf.read()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit-{job_id}.csv"},
        )
    else:
        data = json.dumps(rows, default=str)
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=audit-{job_id}.json"},
        )
