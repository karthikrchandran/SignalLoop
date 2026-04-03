from __future__ import annotations

from app.domain.outreach.template_service import token_density
from app.domain_models import GuardrailViolation, SemanticError

MAX_TOKEN_DENSITY = 0.2
BANNED_PHRASES = {
    "guaranteed results",
    "act now or lose out",
}
REQUIRED_DISCLAIMER_BY_CHANNEL = {
    "email": "unsubscribe",
    "call": "this call may be recorded",
}
CHANNEL_REQUIRED_FIELDS = {
    "email": ["subject"],
    "call": [],
}


def _violation(reason_code: str, message: str) -> GuardrailViolation:
    return GuardrailViolation(
        semantic_error=SemanticError.policy_violation,
        reason_code=reason_code,
        message=message,
    )


def validate_template(channel: str, subject: str | None, content: str) -> list[GuardrailViolation]:
    violations: list[GuardrailViolation] = []
    normalized_channel = channel.lower().strip()
    lower_subject = (subject or "").lower()
    lower_content = content.lower()

    required_disclaimer = REQUIRED_DISCLAIMER_BY_CHANNEL.get(normalized_channel)
    if required_disclaimer and required_disclaimer not in lower_content:
        violations.append(
            _violation(
                "MISSING_REQUIRED_DISCLAIMER",
                f"Template must include required disclaimer for channel {normalized_channel}.",
            )
        )

    for phrase in BANNED_PHRASES:
        if phrase in lower_subject or phrase in lower_content:
            violations.append(
                _violation(
                    "BANNED_PHRASE_PRESENT",
                    f"Template contains disallowed phrase: {phrase}.",
                )
            )

    if token_density(content) > MAX_TOKEN_DENSITY:
        violations.append(
            _violation(
                "TOKEN_DENSITY_EXCEEDED",
                "Template content uses too many personalization tokens for safe publishing.",
            )
        )

    required_fields = CHANNEL_REQUIRED_FIELDS.get(normalized_channel, [])
    if "subject" in required_fields and not (subject and subject.strip()):
        violations.append(
            _violation(
                "CHANNEL_COMPLIANCE_FAILED",
                f"Channel {normalized_channel} requires a non-empty subject.",
            )
        )

    return violations
