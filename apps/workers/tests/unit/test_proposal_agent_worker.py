from __future__ import annotations

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
