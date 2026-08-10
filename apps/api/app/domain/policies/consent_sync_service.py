"""Domain service: ``consent sync service``."""

from __future__ import annotations


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y"}
    return bool(value)


def suppression_reason(contact: dict[str, object]) -> str | None:
    """Suppression reason."""
    if _as_bool(contact.get("suppressed")):
        return "SUPPRESSED_CONTACT"
    if _as_bool(contact.get("doNotContact")):
        return "DO_NOT_CONTACT"
    if not _as_bool(contact.get("consent"), default=False):
        return "CONSENT_MISSING"
    return None


def check_channel_consent(contact: dict[str, object], channel: str) -> bool:
    """Check channel consent."""
    channel_key = f"consent_{channel}"
    if channel_key in contact:
        return _as_bool(contact[channel_key])
    return False


def is_contact_actionable(contact: dict[str, object], channel: str) -> tuple[bool, str | None]:
    """Return ``True`` when contact actionable."""
    reason = suppression_reason(contact)
    if reason is not None:
        return False, reason
    if not check_channel_consent(contact, channel):
        return False, "CONSENT_MISSING"
    return True, None
