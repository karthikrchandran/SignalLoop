from __future__ import annotations


class EnforcementGate:
    def __init__(self, paused: bool = False) -> None:
        self._global_paused = paused
        self._campaign_pause_state: dict[str, bool] = {}

    def is_paused(self) -> bool:
        return self._global_paused

    def set_global_pause(self, paused: bool) -> None:
        self._global_paused = paused

    def set_campaign_pause(self, campaign_id: str, paused: bool) -> None:
        self._campaign_pause_state[campaign_id] = paused

    def can_dequeue(self, campaign_id: str) -> tuple[bool, str | None]:
        if self._global_paused:
            return False, "GLOBAL_PAUSED"
        if self._campaign_pause_state.get(campaign_id, False):
            return False, "CAMPAIGN_PAUSED"
        return True, None
