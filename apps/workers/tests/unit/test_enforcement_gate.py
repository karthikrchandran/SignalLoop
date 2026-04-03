from worker_app.policies.enforcement_gate import EnforcementGate


def test_enforcement_gate_defaults_to_not_paused() -> None:
    assert EnforcementGate().is_paused() is False


def test_enforcement_gate_blocks_dequeue_when_global_pause_enabled() -> None:
    gate = EnforcementGate()
    gate.set_global_pause(True)

    allowed, reason_code = gate.can_dequeue("campaign-1")
    assert allowed is False
    assert reason_code == "GLOBAL_PAUSED"


def test_enforcement_gate_blocks_only_target_campaign_when_campaign_paused() -> None:
    gate = EnforcementGate()
    gate.set_campaign_pause("campaign-1", True)

    allowed_target, reason_target = gate.can_dequeue("campaign-1")
    allowed_other, reason_other = gate.can_dequeue("campaign-2")

    assert allowed_target is False
    assert reason_target == "CAMPAIGN_PAUSED"
    assert allowed_other is True
    assert reason_other is None
