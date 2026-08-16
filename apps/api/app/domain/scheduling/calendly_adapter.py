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
        self,
        account_ref: str,
        credential_secret_ref: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]: ...

    def create_scheduled_event(
        self, payload: dict, idempotency_key: str, credential_secret_ref: str
    ) -> dict: ...

    def update_scheduled_event(
        self,
        event_id: str,
        payload: dict,
        idempotency_key: str,
        credential_secret_ref: str,
    ) -> dict: ...

    def cancel_scheduled_event(
        self,
        event_id: str,
        payload: dict,
        idempotency_key: str,
        credential_secret_ref: str,
    ) -> dict: ...

    def find_scheduled_event(
        self, idempotency_key: str, credential_secret_ref: str
    ) -> dict | None: ...


class CalendlyAdapter:
    """Map a credential-scoped Calendly client to immutable worker contracts."""

    def __init__(self, client: CalendlyClient) -> None:
        self._client = client

    def free_busy(
        self,
        *,
        provider_account_ref: str,
        credential_secret_ref: str,
        start_date: date,
        end_date: date,
    ) -> list[BusyInterval]:
        return [
            BusyInterval(starts_at=item["starts_at"], ends_at=item["ends_at"])
            for item in self._client.get_busy(
                provider_account_ref, credential_secret_ref, start_date, end_date
            )
        ]

    def create_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        raw = self._client.create_scheduled_event(
            command.model_dump(mode="json"),
            command.command_key,
            command.credential_secret_ref,
        )
        return self._receipt(command.command_key, raw)

    def reschedule_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt:
        if command.provider_event_id is None:
            raise ValueError("reschedule requires a provider event")
        raw = self._client.update_scheduled_event(
            command.provider_event_id,
            command.model_dump(mode="json"),
            command.command_key,
            command.credential_secret_ref,
        )
        return self._receipt(command.command_key, raw)

    def cancel_event(self, command: CalendarBookingCommand) -> CalendarProviderReceipt:
        if command.provider_event_id is None:
            raise ValueError("cancellation requires a provider event")
        raw = self._client.cancel_scheduled_event(
            command.provider_event_id,
            command.model_dump(mode="json"),
            command.command_key,
            command.credential_secret_ref,
        )
        return self._receipt(command.command_key, raw)

    def lookup_event(
        self, command_key: str, credential_secret_ref: str
    ) -> CalendarProviderReceipt | None:
        raw = self._client.find_scheduled_event(command_key, credential_secret_ref)
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
