"""Provider-neutral free/busy and event booking contracts."""

from __future__ import annotations

import importlib
import os
from datetime import date, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.scheduling.availability import BusyInterval


class CalendarBookingCommand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "calendar-booking-command.v1"
    command_key: str
    provider_account_ref: str
    credential_secret_ref: str
    operation: str = Field(pattern=r"^(BOOK|RESCHEDULE|CANCEL)$")
    provider_event_id: str | None = None
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
        credential_secret_ref: str,
        start_date: date,
        end_date: date,
    ) -> list[BusyInterval]: ...

    def create_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt: ...

    def reschedule_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt: ...

    def cancel_event(
        self, command: CalendarBookingCommand
    ) -> CalendarProviderReceipt: ...

    def lookup_event(
        self, command_key: str, credential_secret_ref: str
    ) -> CalendarProviderReceipt | None: ...


class CalendarProviderConfigurationError(RuntimeError):
    """No credential-scoped calendar provider factory is configured."""


def load_calendar_provider() -> CalendarProvider:
    """Load a deployment-owned provider without request-supplied secrets."""

    reference = os.environ.get("CALENDAR_PROVIDER_FACTORY", "").strip()
    if ":" not in reference:
        raise CalendarProviderConfigurationError(
            "CALENDAR_PROVIDER_FACTORY must be configured as module:callable"
        )
    module_name, callable_name = reference.split(":", 1)
    factory = getattr(importlib.import_module(module_name), callable_name, None)
    if not callable(factory):
        raise CalendarProviderConfigurationError("calendar provider factory is invalid")
    provider = factory()
    required = (
        "free_busy",
        "create_event",
        "reschedule_event",
        "cancel_event",
        "lookup_event",
    )
    if not all(callable(getattr(provider, name, None)) for name in required):
        raise CalendarProviderConfigurationError(
            "calendar provider contract is incomplete"
        )
    return provider
