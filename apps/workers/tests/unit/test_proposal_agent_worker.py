from __future__ import annotations

import asyncio

from worker_app import main as worker_main
from worker_app import proposal_agent_worker


def test_configured_batch_loads_deployment_owned_adapter(monkeypatch) -> None:
    adapter = object()
    observed: list[object] = []
    monkeypatch.setattr(
        proposal_agent_worker,
        "load_ecrm_proposal_adapter",
        lambda: adapter,
        raising=False,
    )
    monkeypatch.setattr(
        proposal_agent_worker,
        "process_proposal_agent_batch",
        lambda loaded: observed.append(loaded) or 3,
    )

    configured_batch = getattr(
        proposal_agent_worker, "process_configured_proposal_agent_batch", None
    )
    assert configured_batch is not None
    assert configured_batch() == 3
    assert observed == [adapter]


def test_proposal_poll_runs_configured_batch_off_the_event_loop(monkeypatch) -> None:
    observed: list[object] = []

    async def run_in_thread(function):
        observed.append(function)
        return 2

    monkeypatch.setattr(worker_main.asyncio, "to_thread", run_in_thread)
    monkeypatch.setattr(
        worker_main,
        "process_configured_proposal_agent_batch",
        lambda: 2,
        raising=False,
    )

    asyncio.run(worker_main._run_proposal_agent_job())

    assert observed == [worker_main.process_configured_proposal_agent_batch]


def test_main_registers_proposal_agent_poll(monkeypatch) -> None:
    registered: list[dict] = []

    class Scheduler:
        def add_job(self, function, **kwargs):
            registered.append({"function": function, **kwargs})

        def start(self):
            return None

        def shutdown(self):
            return None

    monkeypatch.setattr(worker_main, "AsyncIOScheduler", Scheduler)
    monkeypatch.setattr(
        worker_main.asyncio,
        "get_event_loop",
        lambda: type(
            "Loop", (), {"run_forever": lambda self: (_ for _ in ()).throw(KeyboardInterrupt)}
        )(),
    )

    worker_main.main()

    proposal_jobs = [job for job in registered if job.get("id") == "proposal_agent_worker"]
    assert len(proposal_jobs) == 1
    assert proposal_jobs[0]["function"] is worker_main._run_proposal_agent_job
