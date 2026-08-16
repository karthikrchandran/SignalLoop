"""Calendly-specific mapping behind the provider-neutral calendar contract."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.scheduling.availability import BusyInterval
from app.domain.scheduling.providers import (
    CalendarBookingCommand,
    CalendarProviderReceipt,
)


class CalendlyClient(Protocol):
    def get_busy(
        self, account_ref: str, start_date: date, end_date: date
    ) -> list[dict]: ...

    def create_scheduled_event(self, payload: dict, idempotency_key: str) -> dict: ...

    def find_scheduled_event(self, idempotency_key: str) -> dict | None: ...


class CalendlyAdapter:
    """Map a credential-scoped Calendly client to immutable worker contracts."""

    def __init__(self, client: CalendlyClient) -> None:
        self._client = client

    def free_busy(
        self, *, provider_account_ref: str, start_date: date, end_date: date
    ) -> list[BusyInterval]:
        return [
            BusyInterval(starts_at=item["starts_at"], ends_at=item["ends_at"])
            for item in self._client.get_busy(
                provider_account_ref, start_date, end_date
            )
        ]

    def create_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        raw = self._client.create_scheduled_event(
            command.model_dump(mode="json"), command.command_key
        )
        return self._receipt(command.command_key, raw)

    def lookup_event(self, command_key: str) -> CalendarProviderReceipt | None:
        raw = self._client.find_scheduled_event(command_key)
        return None if raw is None else self._receipt(command_key, raw)

    @staticmethod
    def _receipt(command_key: str, raw: dict) -> CalendarProviderReceipt:
        return CalendarProviderReceipt(
            command_key=command_key,
            provider_event_id=raw["event_id"],
            provider_receipt_id=raw["receipt_id"],
            starts_at=raw["starts_at"],
            ends_at=raw["ends_at"],
        )
