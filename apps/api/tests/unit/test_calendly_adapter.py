from datetime import datetime, timedelta, timezone

from app.domain.scheduling.calendly_adapter import CalendlyAdapter
from app.domain.scheduling.providers import CalendarBookingCommand


class _Client:
    def update_scheduled_event(self, event_id, payload, idempotency_key, secret_ref):
        return _raw(event_id, payload, idempotency_key, secret_ref)

    def cancel_scheduled_event(self, event_id, payload, idempotency_key, secret_ref):
        return _raw(event_id, payload, idempotency_key, secret_ref)


def _raw(event_id, payload, idempotency_key, secret_ref):
    assert event_id == "event-1"
    assert idempotency_key == payload["command_key"]
    assert secret_ref == "secret://calendar/a"
    return {
        "event_id": event_id,
        "receipt_id": f"receipt-{payload['operation'].lower()}",
        "starts_at": payload["starts_at"],
        "ends_at": payload["ends_at"],
    }


def _command(operation: str) -> CalendarBookingCommand:
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    return CalendarBookingCommand(
        command_key=f"command-{operation.lower()}",
        provider_account_ref="calendar-a",
        credential_secret_ref="secret://calendar/a",
        operation=operation,
        provider_event_id="event-1",
        starts_at=starts,
        ends_at=starts + timedelta(minutes=30),
        attendee_email="buyer@example.com",
        title="Discovery",
        timezone="UTC",
        command_digest="a" * 64,
    )


def test_calendly_adapter_maps_reschedule_and_cancel_commands() -> None:
    adapter = CalendlyAdapter(_Client())

    reschedule = adapter.reschedule_event(_command("RESCHEDULE"))
    cancel = adapter.cancel_event(_command("CANCEL"))

    assert reschedule.provider_receipt_id == "receipt-reschedule"
    assert cancel.provider_receipt_id == "receipt-cancel"
