"""Bounded, installation-authorized runner for RevenueOS native projections."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlmodel import Session, select

from app.core.db import engine
from app.domain.installations.projection_dispatch import (
    dispatch_projection_events,
    repair_projection_events,
)
from app.domain.tenants.models import ProductCode, ProductInstallation, Tenant
from app.workers.heartbeat import record_worker_heartbeat

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 30
BATCH_LIMIT = 100


class ProjectionWorker:
    """Processes only active installations and exposes a one-interval runner."""

    def __init__(self, apply: Callable[[object], object]) -> None:
        self._apply = apply

    def run_once(self, session: Session) -> int:
        """Repair stale state then dispatch a bounded batch for active installations."""

        installations = session.exec(
            select(ProductInstallation)
            .join(Tenant, Tenant.id == ProductInstallation.tenant_id)
            .where(
                ProductInstallation.status == "ACTIVE",
                ProductInstallation.product_code == ProductCode.REVENUE_OS,
                Tenant.status == "ACTIVE",
            )
            .order_by("created_at")
            .limit(BATCH_LIMIT)
        ).all()
        processed = 0
        for installation in installations:
            repair_projection_events(session, installation_id=installation.id)
            processed += dispatch_projection_events(
                session, installation_id=installation.id, apply=self._apply
            )
        return processed


def run_once(apply: Callable[[object], object]) -> int:
    """Run one authorized interval; schedulers call this rather than unbounded loops."""

    with Session(engine) as session:
        count = ProjectionWorker(apply).run_once(session)
    record_worker_heartbeat(
        "projection_worker",
        status="healthy",
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
        processed_count=count,
    )
    return count
