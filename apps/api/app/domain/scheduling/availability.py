"""Deterministic timezone-safe calendar availability calculation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalendarAvailabilityError(ValueError):
    """Availability policy or bounded search is invalid."""


class BusyInterval(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def ordered(self) -> BusyInterval:
        if self.ends_at <= self.starts_at:
            raise ValueError("busy interval end must follow start")
        return self


class AvailableSlot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    starts_at: datetime
    ends_at: datetime
    timezone: str


class AvailabilityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timezone: str
    duration_minutes: int = Field(ge=5, le=480)
    working_hours: dict[str, list[list[str]]]
    holiday_dates: set[date] = Field(default_factory=set)
    buffer_before_minutes: int = Field(default=0, ge=0, le=1440)
    buffer_after_minutes: int = Field(default=0, ge=0, le=1440)
    minimum_notice_minutes: int = Field(default=60, ge=0, le=10080)
    slot_interval_minutes: int = Field(default=15, ge=5, le=240)

    @model_validator(mode="after")
    def validate_policy(self) -> AvailabilityPolicy:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise CalendarAvailabilityError(
                "timezone must be a valid IANA zone"
            ) from exc
        for weekday, windows in self.working_hours.items():
            if weekday not in _WEEKDAYS or not windows:
                raise CalendarAvailabilityError(
                    "working hours contain an invalid weekday"
                )
            for window in windows:
                if len(window) != 2 or _parse_time(window[0]) >= _parse_time(window[1]):
                    raise CalendarAvailabilityError(
                        "working-hour windows must be ordered"
                    )
        return self


_WEEKDAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise CalendarAvailabilityError("working-hour time must use HH:MM") from exc


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise CalendarAvailabilityError("calendar timestamps must include timezone")
    return value.astimezone(timezone.utc)


def calculate_available_slots(
    *,
    policy: AvailabilityPolicy,
    start_date: date,
    end_date: date,
    busy: list[BusyInterval],
    now: datetime | None = None,
    limit: int = 50,
) -> list[AvailableSlot]:
    """Calculate bounded UTC slots from local working-hour policy and free/busy."""

    if (
        end_date < start_date
        or (end_date - start_date).days > 31
        or not 1 <= limit <= 200
    ):
        raise CalendarAvailabilityError(
            "availability range must be ordered and at most 31 days"
        )
    zone = ZoneInfo(policy.timezone)
    at = _utc(now or datetime.now(timezone.utc))
    earliest = at + timedelta(minutes=policy.minimum_notice_minutes)
    before = timedelta(minutes=policy.buffer_before_minutes)
    after = timedelta(minutes=policy.buffer_after_minutes)
    duration = timedelta(minutes=policy.duration_minutes)
    step = timedelta(minutes=policy.slot_interval_minutes)
    normalized_busy = [(_utc(item.starts_at), _utc(item.ends_at)) for item in busy]
    slots: list[AvailableSlot] = []
    current_date = start_date
    while current_date <= end_date and len(slots) < limit:
        weekday = _WEEKDAYS[current_date.weekday()]
        if current_date not in policy.holiday_dates:
            for start_text, end_text in policy.working_hours.get(weekday, []):
                cursor = datetime.combine(current_date, _parse_time(start_text), zone)
                local_end = datetime.combine(current_date, _parse_time(end_text), zone)
                while cursor + duration <= local_end and len(slots) < limit:
                    start_utc = cursor.astimezone(timezone.utc)
                    end_utc = (cursor + duration).astimezone(timezone.utc)
                    conflicts = any(
                        start_utc - before < busy_end and end_utc + after > busy_start
                        for busy_start, busy_end in normalized_busy
                    )
                    if start_utc >= earliest and not conflicts:
                        slots.append(
                            AvailableSlot(
                                starts_at=start_utc,
                                ends_at=end_utc,
                                timezone=policy.timezone,
                            )
                        )
                    cursor += step
        current_date += timedelta(days=1)
    return slots
