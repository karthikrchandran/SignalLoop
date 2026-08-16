"""Provider-neutral free/busy and event booking contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.scheduling.availability import BusyInterval


class CalendarBookingCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "calendar-booking-command.v1"
    command_key: str
    provider_account_ref: str
    starts_at: datetime
    ends_at: datetime
    attendee_email: str
    title: str
    timezone: str
    command_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


class CalendarProviderReceipt(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "calendar-provider-receipt.v1"
    command_key: str
    provider_event_id: str
    provider_receipt_id: str
    starts_at: datetime
    ends_at: datetime


class CalendarProvider(Protocol):
    def free_busy(
        self,
        *,
        provider_account_ref: str,
        start_date: date,
        end_date: date,
    ) -> list[BusyInterval]: ...

    def create_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt: ...

    def lookup_event(self, command_key: str) -> CalendarProviderReceipt | None: ...
