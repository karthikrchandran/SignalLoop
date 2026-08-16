"""Scheduled adapter for durable Calendar Scheduler Agent jobs."""

from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_SRC = _REPO_ROOT / "apps" / "api"
if str(_API_SRC) not in sys.path:
    sys.path.insert(0, str(_API_SRC))

from sqlmodel import Session  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.domain.scheduling.providers import CalendarProvider  # noqa: E402
from app.domain.scheduling.worker import (  # noqa: E402
    recover_expired_booking_leases,
    run_calendar_booking_batch,
)

logger = logging.getLogger(__name__)

CALENDAR_SCHEDULER_POLL_INTERVAL_SECONDS = 30
CALENDAR_SCHEDULER_BATCH_SIZE = 25


class CalendarSchedulerConfigurationError(RuntimeError):
    """The deployment has not supplied a credential-scoped provider factory."""


def load_calendar_provider() -> CalendarProvider:
    """Load an explicit deployment-owned provider factory; never use inline secrets."""

    reference = os.environ.get("CALENDAR_PROVIDER_FACTORY", "").strip()
    if ":" not in reference:
        raise CalendarSchedulerConfigurationError(
            "CALENDAR_PROVIDER_FACTORY must be configured as module:callable"
        )
    module_name, callable_name = reference.split(":", 1)
    factory = getattr(importlib.import_module(module_name), callable_name, None)
    if not callable(factory):
        raise CalendarSchedulerConfigurationError(
            "calendar provider factory is invalid"
        )
    provider = factory()
    if not all(
        callable(getattr(provider, name, None))
        for name in ("free_busy", "create_event", "lookup_event")
    ):
        raise CalendarSchedulerConfigurationError(
            "calendar provider contract is incomplete"
        )
    return provider


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
