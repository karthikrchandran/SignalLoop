"""Audit log query and export API for Story 5.2."""
from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import UTC, datetime
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

EXPORT_FIELDNAMES = [
    "id",
    "event_name",
    "workspace_id",
    "actor_id",
    "actor_role",
    "resource_type",
    "resource_id",
    "correlation_id",
    "payload",
    "created_at",
]

# ---------------------------------------------------------------------------
# In-process export job registry (MVP – single-process only)
# ---------------------------------------------------------------------------
_export_jobs: dict[str, dict[str, Any]] = {}


def _audit_filters(
    *,
    workspace_id: str,
    actor_id: uuid.UUID | None = None,
    action_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    correlation_id: str | None = None,
) -> list[Any]:
    filters: list[Any] = [AuditEvent.workspace_id == workspace_id]
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
    return filters


def _event_row(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_name": event.event_name,
        "workspace_id": event.workspace_id,
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_role": event.actor_role,
        "resource_type": event.resource_type,
        "resource_id": event.resource_id,
        "correlation_id": event.correlation_id,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


def _iter_export_rows(session: SessionDep, job: dict[str, Any]):
    offset = 0
    batch_size = 500
    filters = _audit_filters(
        workspace_id=job["workspace_id"],
        actor_id=uuid.UUID(job["actor_id_filter"]) if job.get("actor_id_filter") else None,
        action_type=job.get("action_type"),
        from_date=job.get("from_date"),
        to_date=job.get("to_date"),
        correlation_id=job.get("correlation_id"),
    )
    while True:
        events = session.exec(
            select(AuditEvent)
            .where(and_(*filters))
            .order_by(AuditEvent.created_at.desc())
            .offset(offset)
            .limit(batch_size)
        ).all()
        if not events:
            break
        for event in events:
            yield _event_row(event)
        offset += len(events)


def _stream_json_export(session: SessionDep, job: dict[str, Any]):
    yield "["
    first = True
    for row in _iter_export_rows(session, job):
        if not first:
            yield ","
        first = False
        yield json.dumps(row, default=str)
    yield "]"


def _stream_csv_export(session: SessionDep, job: dict[str, Any]):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES)
    writer.writeheader()
    yield buffer.getvalue()
    for row in _iter_export_rows(session, job):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDNAMES)
        writer.writerow({**row, "payload": json.dumps(row["payload"], default=str)})
        yield buffer.getvalue()


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
    """Return a list of audit events."""
    filters = _audit_filters(
        workspace_id=workspace_id,
        actor_id=actor_id,
        action_type=action_type,
        from_date=from_date,
        to_date=to_date,
        correlation_id=correlation_id,
    )

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
    workspace_id: WorkspaceIdDep,
    current_user: CurrentUser,
    format: Annotated[str, Body(pattern="^(json|csv)$", embed=True)] = "json",
    actor_id: Annotated[uuid.UUID | None, Body(embed=True)] = None,
    action_type: Annotated[str | None, Body(embed=True)] = None,
    from_date: Annotated[datetime | None, Body(embed=True)] = None,
    to_date: Annotated[datetime | None, Body(embed=True)] = None,
    correlation_id: Annotated[str | None, Body(embed=True)] = None,
) -> dict[str, str]:
    """Create export job."""
    job_id = str(uuid.uuid4())
    _export_jobs[job_id] = {
        "status": "complete",
        "format": format,
        "workspace_id": workspace_id,
        "created_by": str(current_user.id),
        "created_at": datetime.now(UTC),
        "actor_id_filter": str(actor_id) if actor_id else None,
        "action_type": action_type,
        "from_date": from_date,
        "to_date": to_date,
        "correlation_id": correlation_id,
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
    session: SessionDep,
    job_id: str,
    workspace_id: WorkspaceIdDep,
) -> StreamingResponse:
    """Download export."""
    job = _export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    if job["workspace_id"] != workspace_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    fmt: str = job["format"]

    if fmt == "csv":
        return StreamingResponse(
            _stream_csv_export(session, job),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit-{job_id}.csv"},
        )
    else:
        return StreamingResponse(
            _stream_json_export(session, job),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=audit-{job_id}.json"},
        )
