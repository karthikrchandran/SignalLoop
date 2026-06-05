"""Worker heartbeat persistence helpers."""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlmodel import Session

from app.core.db import engine
from app.domain_models import WorkerHeartbeat

logger = logging.getLogger(__name__)


def record_worker_heartbeat(
    worker_key: str,
    *,
    status: str,
    poll_interval_seconds: int,
    processed_count: int | None = None,
    error_message: str | None = None,
) -> None:
    """Persist the current heartbeat for a worker.

    Failures are logged and swallowed so worker loops keep running.
    """

    try:
        with Session(engine) as session:
            row = session.get(WorkerHeartbeat, worker_key)
            now = datetime.now(timezone.utc)
            if row is None:
                row = WorkerHeartbeat(worker_key=worker_key)

            row.status = status
            row.poll_interval_seconds = poll_interval_seconds
            row.last_seen_at = now
            row.updated_at = now

            if processed_count is not None:
                row.last_processed_count = processed_count

            if status == "healthy":
                row.last_success_at = now
                row.last_error_message = None
            elif status == "error":
                row.last_error_at = now
                row.last_error_message = (error_message or "worker_error")[:500]

            session.add(row)
            session.commit()
    except Exception:
        logger.exception("Failed to persist worker heartbeat for %s", worker_key)