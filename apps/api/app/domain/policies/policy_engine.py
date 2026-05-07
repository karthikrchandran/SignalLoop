"""Module: ``policy engine``."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain_models import GovernancePolicy, PolicyDecision, PolicyType, SemanticError


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _contact_timezone(contact: dict, fallback: str = "UTC") -> ZoneInfo:
    timezone_name = str(contact.get("timezone") or fallback)
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _in_quiet_hours(*, local_now: datetime, start: time, end: time) -> bool:
    now_time = local_now.time()
    if start <= end:
        return start <= now_time <= end
    return now_time >= start or now_time <= end


def _next_eligible_at(*, requested_at: datetime, local_now: datetime, end: time) -> datetime:
    candidate_local = local_now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
    if candidate_local <= local_now:
        candidate_local = candidate_local + timedelta(days=1)
    return candidate_local.astimezone(requested_at.tzinfo or UTC)


def _is_suppressed(contact: dict) -> bool:
    if bool(contact.get("suppressed", False)):
        return True
    if bool(contact.get("do_not_contact", False)):
        return True
    consent = contact.get("consent")
    if consent is False:
        return True
    return False


def evaluate_policies(*, policies: list[GovernancePolicy], contact: dict, campaign_daily_count: int, system_daily_count: int, requested_at: datetime | None = None) -> PolicyDecision:
    """Evaluate policies."""
    requested_at = _normalize_datetime(requested_at or datetime.now(UTC))

    for policy in policies:
        payload = policy.payload_json

        if policy.policy_type == PolicyType.suppression and _is_suppressed(contact):
            return PolicyDecision(
                allowed=False,
                semantic_error=SemanticError.policy_violation,
                reason_code="SUPPRESSED_CONTACT",
            )

        if policy.policy_type == PolicyType.quiet_hours:
            tz = _contact_timezone(contact, str(payload.get("timezone", "UTC")))
            local_now = requested_at.astimezone(tz)
            start = time.fromisoformat(str(payload.get("start", "21:00")))
            end = time.fromisoformat(str(payload.get("end", "08:00")))
            if _in_quiet_hours(local_now=local_now, start=start, end=end):
                return PolicyDecision(
                    allowed=False,
                    semantic_error=SemanticError.policy_violation,
                    reason_code="QUIET_HOURS_BLOCK",
                    next_eligible_at=_next_eligible_at(requested_at=requested_at, local_now=local_now, end=end),
                )

        if policy.policy_type == PolicyType.daily_caps:
            system_cap = int(payload.get("systemDailyCap", payload.get("systemCap", 999999)))
            campaign_cap = int(payload.get("campaignDailyCap", payload.get("campaignCap", 999999)))
            if system_daily_count >= system_cap:
                return PolicyDecision(
                    allowed=False,
                    semantic_error=SemanticError.policy_violation,
                    reason_code="SYSTEM_CAP_EXCEEDED",
                )
            if campaign_daily_count >= campaign_cap:
                return PolicyDecision(
                    allowed=False,
                    semantic_error=SemanticError.policy_violation,
                    reason_code="CAMPAIGN_CAP_EXCEEDED",
                )

    return PolicyDecision(allowed=True)
