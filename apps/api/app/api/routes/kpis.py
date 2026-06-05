"""KPI summary endpoints — Story 5.4: Provide KPI Summaries for Weekly Operating Rhythm."""
from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import SessionDep
from app.api.request_context import WorkspaceIdDep
from app.domain.reporting.kpi_aggregation_service import (
    Granularity,
    get_kpi_summary,
    get_kpi_trend,
)

router = APIRouter(prefix="/workspaces/{ws_id}/kpis", tags=["kpis"])

_KPI_CACHE_TTL = 600  # 10 minutes
_KPI_CACHE_VERSION = "v2"


def _cache_key(
    ws_id: str,
    start: date,
    end: date,
    granularity: str,
    campaign_id: uuid.UUID | None,
) -> str:
    base = f"kpi:{_KPI_CACHE_VERSION}:{ws_id}:{start}:{end}:{granularity}"
    if campaign_id is not None:
        base += f":{campaign_id.hex}"
    return base


async def _get_cached(request: Request, key: str) -> dict | None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return None
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception:  # noqa: BLE001
        pass
    return None


async def _set_cached(request: Request, key: str, data: dict) -> None:
    try:
        redis = request.app.state.redis_manager.client
        if redis is None:
            return
        await redis.setex(key, _KPI_CACHE_TTL, json.dumps(data, default=str))
    except Exception:  # noqa: BLE001
        pass


def _ensure_workspace_path_matches_header(ws_id: str, workspace_id: str) -> None:
    if ws_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Workspace mismatch")


@router.get("/summary")
async def get_kpi_summary_endpoint(
    *,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    ws_id: str,
    start: Annotated[date, Query(description="Start date (YYYY-MM-DD)")],
    end: Annotated[date, Query(description="End date (YYYY-MM-DD)")],
    granularity: Annotated[Granularity, Query(description="Bucket granularity")] = "weekly",
    campaign_id: Annotated[uuid.UUID | None, Query(description="Filter by campaign")] = None,
) -> dict:
    """Return current-period KPIs, prior-period KPIs, and period-over-period delta_pct."""
    _ensure_workspace_path_matches_header(ws_id, workspace_id)

    # --- Validation ---
    if start > end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start must be <= end")

    cache_key = _cache_key(ws_id, start, end, granularity, campaign_id)
    cached = await _get_cached(request, cache_key)
    if cached is not None:
        return cached

    result = get_kpi_summary(session, ws_id, start, end, granularity, campaign_id)
    await _set_cached(request, cache_key, result)
    return result


@router.get("/trend")
async def get_kpi_trend_endpoint(
    *,
    request: Request,
    session: SessionDep,
    workspace_id: WorkspaceIdDep,
    ws_id: str,
    start: Annotated[date, Query(description="Start date (YYYY-MM-DD)")],
    end: Annotated[date, Query(description="End date (YYYY-MM-DD)")],
    granularity: Annotated[Granularity, Query(description="Bucket granularity")] = "weekly",
    campaign_id: Annotated[uuid.UUID | None, Query(description="Filter by campaign")] = None,
) -> list[dict]:
    """Return bucketed KPI trend data points for charting."""
    _ensure_workspace_path_matches_header(ws_id, workspace_id)

    # --- Validation ---
    if start > end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start must be <= end")

    trend_cache_key = _cache_key(ws_id, start, end, f"trend_{granularity}", campaign_id)
    cached = await _get_cached(request, trend_cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    buckets = get_kpi_trend(session, ws_id, start, end, granularity, campaign_id)
    await _set_cached(request, trend_cache_key, buckets)  # type: ignore[arg-type]
    return buckets
