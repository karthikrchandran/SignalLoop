"""Operational durable eCRM installation projection worker."""

from __future__ import annotations

import argparse
import logging
import signal
from collections.abc import Callable
from threading import Event
from typing import Protocol

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.service import InstallationProjectionWorker
from app.workers.heartbeat import record_worker_heartbeat

logger = logging.getLogger(__name__)
WORKER_KEY = "ecrm_installation_projection_worker"


class StopEvent(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float) -> bool: ...


def run(*, workspace_id: str | None = None, limit: int = 100) -> dict[str, int]:
    with Session(engine) as session:
        return InstallationProjectionWorker(EcrmInstallationRepository(session)).run_once(
            workspace_id=workspace_id, limit=limit
        )


def run_loop(
    *,
    stop_event: StopEvent,
    poll_interval_seconds: int,
    batch_size: int,
    run_batch: Callable[[int], dict[str, int]] | None = None,
    heartbeat: Callable[..., None] | None = None,
) -> None:
    """Process all due states until a graceful shutdown is requested."""
    if poll_interval_seconds < 1:
        raise ValueError("poll_interval_seconds must be positive")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batch = run_batch or (lambda limit: run(limit=limit))

    def default_heartbeat(
        status: str,
        processed_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        record_worker_heartbeat(
            WORKER_KEY,
            status=status,
            poll_interval_seconds=poll_interval_seconds,
            processed_count=processed_count,
            error_message=error_message,
        )

    emit = heartbeat or default_heartbeat
    processed_count: int | None = None
    emit("starting")
    try:
        while not stop_event.is_set():
            try:
                result = batch(batch_size)
                processed_count = sum(result.values())
                emit("healthy", processed_count=processed_count)
            except Exception as exc:
                emit("error", error_message=type(exc).__name__)
                logger.exception("Installation projection worker loop error")
            if stop_event.wait(poll_interval_seconds):
                break
    finally:
        emit("stopped", processed_count=processed_count)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable eCRM installation projections")
    parser.add_argument("--workspace-id")
    parser.add_argument(
        "--limit",
        "--batch-size",
        dest="limit",
        type=int,
        default=settings.ECRM_INSTALLATION_PROJECTION_BATCH_SIZE,
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=settings.ECRM_INSTALLATION_PROJECTION_POLL_INTERVAL_SECONDS,
    )
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        print(run(workspace_id=args.workspace_id, limit=args.limit))  # noqa: T201
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    stop_event = Event()

    def request_stop(signum: int, frame: object) -> None:  # noqa: ARG001
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    run_loop(
        stop_event=stop_event,
        poll_interval_seconds=args.poll_interval,
        batch_size=args.limit,
        run_batch=lambda limit: run(workspace_id=args.workspace_id, limit=limit),
    )


if __name__ == "__main__":
    main()
