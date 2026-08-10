"""Domain service: ``consent sync service``."""

from __future__ import annotations

from collections.abc import Mapping


def _as_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _first(contact: Mapping[str, object], *keys: str) -> tuple[bool, object | None]:
    for key in keys:
        if key in contact:
            return True, contact[key]
    return False, None


def suppression_reason(contact: Mapping[str, object]) -> str | None:
    """Suppression reason."""
    if _as_bool(contact.get("suppressed")):
        return "SUPPRESSED_CONTACT"
    _, do_not_contact = _first(contact, "do_not_contact", "doNotContact")
    if _as_bool(do_not_contact):
        return "DO_NOT_CONTACT"
    if "consent" in contact and not _as_bool(contact.get("consent"), default=False):
        return "CONSENT_MISSING"
    return None


def check_channel_consent(contact: Mapping[str, object], channel: str) -> bool:
    """Check channel consent."""
    camel_key = f"consent{channel.title()}"
    found, value = _first(contact, f"consent_{channel}", camel_key)
    if found:
        return _as_bool(value)
    return False


def is_contact_actionable(
    contact: Mapping[str, object], channel: str
) -> tuple[bool, str | None]:
    """Return ``True`` when contact actionable."""
    reason = suppression_reason(contact)
    if reason is not None:
        return False, reason
    if not check_channel_consent(contact, channel):
        return False, "CONSENT_MISSING"
    return True, None
