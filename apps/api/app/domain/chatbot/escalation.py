"""Escalation detection for ChatBot Hub runtime."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.chatbot.models import ChatbotBotConfig, ChatbotConversation

DEFAULT_CONFIDENCE_THRESHOLD = 0.25
LOW_CONFIDENCE_STREAK_LIMIT = 3

HUMAN_REQUEST_PHRASES = {
    "agent",
    "human",
    "person",
    "representative",
    "talk to someone",
    "speak to someone",
    "speak with someone",
    "connect me",
    "call me",
}


@dataclass(frozen=True)
class EscalationDecision:
    """Result of escalation evaluation."""

    should_escalate: bool
    reason: str | None = None
    out_of_hours: bool = False


def confidence_threshold(bot_config: ChatbotBotConfig) -> float:
    """Return configured confidence threshold with a safe default."""
    raw = bot_config.lead_capture_json.get("confidence_threshold")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_CONFIDENCE_THRESHOLD
    return min(1.0, max(0.0, value))


def explicit_human_request(text: str | None) -> bool:
    """Return true when the visitor clearly requests a human."""
    normalized = (text or "").lower()
    return any(phrase in normalized for phrase in HUMAN_REQUEST_PHRASES)


def is_outside_business_hours(bot_config: ChatbotBotConfig, now: datetime | None = None) -> bool:
    """Evaluate optional business-hours rules stored on the bot config."""
    config = bot_config.business_hours_json or {}
    if not config.get("enabled"):
        return False

    timezone_name = str(config.get("timezone") or "UTC")
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    local_now = (now or datetime.now(tz)).astimezone(tz)
    allowed_days = config.get("days") or config.get("business_hours_days") or [0, 1, 2, 3, 4]
    if local_now.weekday() not in {int(day) for day in allowed_days}:
        return True

    start = str(config.get("start") or config.get("business_hours_start") or "09:00")
    end = str(config.get("end") or config.get("business_hours_end") or "17:00")
    current_hm = local_now.strftime("%H:%M")
    return not (start <= current_hm <= end)


def evaluate_escalation(
    *,
    text: str | None,
    confidence: float,
    conversation: ChatbotConversation,
    bot_config: ChatbotBotConfig,
    now: datetime | None = None,
) -> EscalationDecision:
    """Return whether this turn should route to human handoff."""
    if explicit_human_request(text):
        return EscalationDecision(True, "human_requested")

    if is_outside_business_hours(bot_config, now):
        return EscalationDecision(True, "outside_business_hours", out_of_hours=True)

    threshold = confidence_threshold(bot_config)
    if confidence < threshold:
        if conversation.consecutive_low_confidence_count + 1 >= LOW_CONFIDENCE_STREAK_LIMIT:
            return EscalationDecision(True, "low_confidence_streak")
        return EscalationDecision(True, "low_confidence")

    return EscalationDecision(False)

