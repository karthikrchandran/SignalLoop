"""Restart-safe worker for durable RevenueOS intervention dispatches."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.revenue_intelligence.dispatcher import (  # noqa: E402
    InterventionDelivery,
    RevenueInterventionDispatcher,
)
from app.domain.revenue_intelligence.enforcement import (  # noqa: E402
    ConfiguredInterventionEnforcementGate,
)
from app.domain.revenue_intelligence.persistence import RevenueInterventionStore  # noqa: E402
from app.domain.revenue_intelligence.persistence_models import (  # noqa: E402
    RevenueInterventionDispatch,
)
from app.domain.revenue_intelligence.provider_delivery import (  # noqa: E402
    ConfiguredEmailInterventionDelivery,
)
from app.domain.tenants.models import ProductCode, ProductInstallation, utc_now  # noqa: E402

logger = logging.getLogger(__name__)

REVENUE_INTERVENTION_POLL_INTERVAL_SECONDS = 30
REVENUE_INTERVENTION_BATCH_SIZE = 100

DeliveryFactory = Callable[[Session, str], InterventionDelivery]


async def process_claimed_revenue_interventions(
    session: Session,
    *,
    delivery_factory: DeliveryFactory | None = None,
    batch_size: int = REVENUE_INTERVENTION_BATCH_SIZE,
) -> int:
    """Recover abandoned leases, claim due dispatches, and settle them."""
    store = RevenueInterventionStore(session)
    recovered = store.recover_expired_dispatch_leases()
    if recovered:
        logger.warning("Recovered %d expired RevenueOS dispatch lease(s)", recovered)

    processed = 0
    for tenant_id in _tenant_ids_with_due_dispatches(session):
        if processed >= batch_size:
            break
        installation = _signal_loop_installation(session, tenant_id)
        claimed = store.claim_due_dispatches(
            tenant_id=tenant_id,
            limit=batch_size - processed,
        )
        for dispatch in claimed:
            processed += 1
            if installation is None:
                store.record_dispatch_failure(
                    tenant_id=tenant_id,
                    dispatch_id=dispatch.id,
                    provider="configuration",
                    reason="SIGNAL_LOOP_INSTALLATION_REQUIRED",
                    retryable=False,
                )
                continue
            store.prepare_dispatch_attempt(
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                workspace_id=installation.local_identifier,
            )
            delivery = (
                delivery_factory(session, installation.local_identifier)
                if delivery_factory is not None
                else ConfiguredEmailInterventionDelivery(
                    session=session,
                    workspace_id=installation.local_identifier,
                )
            )
            await RevenueInterventionDispatcher(
                delivery,
                enforcement_gate=ConfiguredInterventionEnforcementGate(
                    session=session,
                    workspace_id=installation.local_identifier,
                ),
            ).dispatch(
                store,
                tenant_id=tenant_id,
                dispatch_id=dispatch.id,
                workspace_id=installation.local_identifier,
            )
    return processed


async def process_revenue_intervention_batch() -> int:
    """Execute one scheduled RevenueOS intervention cycle against the database."""
    with Session(engine) as session:
        return await process_claimed_revenue_interventions(session)


def _tenant_ids_with_due_dispatches(session: Session) -> list[UUID]:
    now = utc_now()
    return list(
        session.exec(
            select(RevenueInterventionDispatch.tenant_id)
            .where(
                RevenueInterventionDispatch.status.in_(("PENDING", "RETRY_SCHEDULED")),
                (RevenueInterventionDispatch.next_attempt_at.is_(None))
                | (RevenueInterventionDispatch.next_attempt_at <= now),
            )
            .distinct()
        ).all()
    )


def _signal_loop_installation(
    session: Session, tenant_id: UUID
) -> ProductInstallation | None:
    return session.exec(
        select(ProductInstallation).where(
            ProductInstallation.tenant_id == tenant_id,
            ProductInstallation.product_code == ProductCode.SIGNAL_LOOP,
            ProductInstallation.status == "ACTIVE",
        )
    ).one_or_none()
