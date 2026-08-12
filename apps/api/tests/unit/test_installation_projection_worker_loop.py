from __future__ import annotations

from app.workers import installation_projection_worker


class StopAfterFirstWait:
    def __init__(self) -> None:
        self.stopped = False
        self.waits: list[float] = []

    def is_set(self) -> bool:
        return self.stopped

    def wait(self, timeout: float) -> bool:
        self.waits.append(timeout)
        self.stopped = True
        return True


def test_worker_loop_runs_batch_heartbeats_and_stops_gracefully() -> None:
    stop = StopAfterFirstWait()
    batches: list[int] = []
    heartbeats: list[tuple[str, int | None]] = []

    installation_projection_worker.run_loop(
        stop_event=stop,
        poll_interval_seconds=7,
        batch_size=23,
        run_batch=lambda limit: batches.append(limit) or {"applied": 1, "held": 1, "failed": 1},
        heartbeat=lambda status, processed_count=None, error_message=None: heartbeats.append(
            (status, processed_count)
        ),
    )

    assert batches == [23]
    assert stop.waits == [7]
    assert heartbeats == [("starting", None), ("healthy", 3), ("stopped", 3)]
