import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from worker_app.call_worker import POLL_INTERVAL_SECONDS as CALL_POLL_INTERVAL_SECONDS
from worker_app.call_worker import poll_and_dispatch
from worker_app.policies.enforcement_gate import EnforcementGate
from worker_app.postcall_worker import process_completed_calls
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

    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down scheduler")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
