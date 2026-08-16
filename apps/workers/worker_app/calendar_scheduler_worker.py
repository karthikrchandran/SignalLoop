"""Scheduled adapter for durable Calendar Scheduler Agent jobs."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.scheduling.providers import (  # noqa: E402
    CalendarProvider,
    CalendarProviderConfigurationError,
    load_calendar_provider,
)
from app.domain.scheduling.worker import (  # noqa: E402
    recover_expired_booking_leases,
    run_calendar_booking_batch,
)

logger = logging.getLogger(__name__)

CALENDAR_SCHEDULER_POLL_INTERVAL_SECONDS = 30
CALENDAR_SCHEDULER_BATCH_SIZE = 25


CalendarSchedulerConfigurationError = CalendarProviderConfigurationError


def process_calendar_scheduler_batch(provider: CalendarProvider) -> int:
    """Recover safe leases and process one bounded provider-backed batch."""

    with Session(engine) as session:
        recovered = recover_expired_booking_leases(session)
        if recovered:
            session.commit()
            logger.warning("Recovered %d calendar booking lease(s)", recovered)
        return run_calendar_booking_batch(
            session,
            provider=provider,
            limit=CALENDAR_SCHEDULER_BATCH_SIZE,
        )


def process_configured_calendar_scheduler_batch() -> int:
    """Load the deployment provider and process one recoverable calendar batch."""

    return process_calendar_scheduler_batch(load_calendar_provider())
