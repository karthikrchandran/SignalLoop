import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from worker_app.calendar_scheduler_worker import (
    CALENDAR_SCHEDULER_POLL_INTERVAL_SECONDS,
    CalendarSchedulerConfigurationError,
    load_calendar_provider,
    process_calendar_scheduler_batch,
)
from worker_app.call_worker import POLL_INTERVAL_SECONDS as CALL_POLL_INTERVAL_SECONDS
from worker_app.call_worker import poll_and_dispatch
from worker_app.lead_preparation_worker import (
    LEAD_PREPARATION_POLL_INTERVAL_SECONDS,
    process_lead_preparation_batch,
)
from worker_app.policies.enforcement_gate import EnforcementGate
from worker_app.postcall_worker import process_completed_calls
from worker_app.projection_worker import (
    PROJECTION_POLL_INTERVAL_SECONDS,
    ProjectionWorkerConfigurationError,
    process_projection_batch,
)
from worker_app.revenue_intervention_worker import (
    REVENUE_INTERVENTION_POLL_INTERVAL_SECONDS,
    process_revenue_intervention_batch,
)
from worker_app.sequence_worker import POLL_INTERVAL_SECONDS, process_batch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POSTCALL_POLL_INTERVAL_SECONDS = 60
# call_worker uses its own constant (30 s); imported above as CALL_POLL_INTERVAL_SECONDS


async def _run_batch_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping poll")
        return
    try:
        count = await process_batch()
        if count:
            logger.info("Sequence worker processed %d contact(s)", count)
    except Exception:
        logger.exception("Sequence worker poll failed")


async def _run_call_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping call poll")
        return
    try:
        await poll_and_dispatch()
    except Exception:
        logger.exception("Call worker poll failed")


async def _run_postcall_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping postcall poll")
        return
    try:
        await process_completed_calls()
    except Exception:
        logger.exception("Postcall worker poll failed")


async def _run_projection_job() -> None:
    try:
        count = process_projection_batch()
        if count:
            logger.info("Projection worker processed %d projection(s)", count)
    except ProjectionWorkerConfigurationError as exc:
        logger.warning("Projection worker blocked by configuration: %s", exc)
    except Exception:
        logger.exception("Projection worker poll failed")


async def _run_revenue_intervention_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping RevenueOS intervention poll")
        return
    try:
        count = await process_revenue_intervention_batch()
        if count:
            logger.info("RevenueOS worker processed %d intervention dispatch(es)", count)
    except Exception:
        logger.exception("RevenueOS intervention worker poll failed")


async def _run_lead_preparation_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping lead preparation poll")
        return
    try:
        count = process_lead_preparation_batch()
        if count:
            logger.info("Lead preparation worker processed %d job(s)", count)
    except Exception:
        logger.exception("Lead preparation worker poll failed")


async def _run_calendar_scheduler_job() -> None:
    gate = EnforcementGate()
    if gate.is_paused():
        logger.info("EnforcementGate paused — skipping calendar scheduler poll")
        return
    try:
        count = process_calendar_scheduler_batch(load_calendar_provider())
        if count:
            logger.info("Calendar scheduler processed %d booking job(s)", count)
    except CalendarSchedulerConfigurationError as exc:
        logger.warning("Calendar scheduler blocked by configuration: %s", exc)
    except Exception:
        logger.exception("Calendar scheduler poll failed")


def main() -> None:
    gate = EnforcementGate()
    logger.info("SignalLoop worker initializing (paused=%s)", gate.is_paused())

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _run_batch_job,
        trigger="interval",
        seconds=POLL_INTERVAL_SECONDS,
        id="sequence_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_call_job,
        trigger="interval",
        seconds=CALL_POLL_INTERVAL_SECONDS,
        id="call_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_postcall_job,
        trigger="interval",
        seconds=POSTCALL_POLL_INTERVAL_SECONDS,
        id="postcall_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_projection_job,
        trigger="interval",
        seconds=PROJECTION_POLL_INTERVAL_SECONDS,
        id="projection_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_revenue_intervention_job,
        trigger="interval",
        seconds=REVENUE_INTERVENTION_POLL_INTERVAL_SECONDS,
        id="revenue_intervention_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_lead_preparation_job,
        trigger="interval",
        seconds=LEAD_PREPARATION_POLL_INTERVAL_SECONDS,
        id="lead_preparation_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_calendar_scheduler_job,
        trigger="interval",
        seconds=CALENDAR_SCHEDULER_POLL_INTERVAL_SECONDS,
        id="calendar_scheduler_worker",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Sequence worker scheduled (interval=%ds)", POLL_INTERVAL_SECONDS
    )
    logger.info(
        "Call worker scheduled (interval=%ds)", CALL_POLL_INTERVAL_SECONDS
    )
    logger.info(
        "Postcall worker scheduled (interval=%ds)", POSTCALL_POLL_INTERVAL_SECONDS
    )
    logger.info(
        "Projection worker scheduled (interval=%ds)", PROJECTION_POLL_INTERVAL_SECONDS
    )
    logger.info(
        "RevenueOS intervention worker scheduled (interval=%ds)",
        REVENUE_INTERVENTION_POLL_INTERVAL_SECONDS,
    )
    logger.info(
        "Lead preparation worker scheduled (interval=%ds)",
        LEAD_PREPARATION_POLL_INTERVAL_SECONDS,
    )
    logger.info(
        "Calendar scheduler scheduled (interval=%ds)",
        CALENDAR_SCHEDULER_POLL_INTERVAL_SECONDS,
    )

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
