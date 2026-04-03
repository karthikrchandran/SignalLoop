from app.domain.policies.template_guardrail_service import validate_template


def test_validate_template_returns_reason_coded_guardrail_violations() -> None:
    violations = validate_template(
        "email",
        None,
        (
            "Guaranteed results for {{contact.firstName}} {{contact.company}} "
            "{{contact.timezone}}. Act now or lose out."
        ),
    )

    reason_codes = {violation.reason_code for violation in violations}
    assert "MISSING_REQUIRED_DISCLAIMER" in reason_codes
    assert "BANNED_PHRASE_PRESENT" in reason_codes
    assert "TOKEN_DENSITY_EXCEEDED" in reason_codes
    assert "CHANNEL_COMPLIANCE_FAILED" in reason_codes


def test_validate_template_passes_when_email_content_is_compliant() -> None:
    compliant_content = (
        "Hello {{contact.firstName}}, this is your update. "
        "To opt out, use the unsubscribe link below."
    )

    violations = validate_template("email", "Monthly update", compliant_content)
    assert violations == []
