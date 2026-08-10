from app.domain.policies.consent_sync_service import is_contact_actionable


def test_missing_consent_is_not_actionable() -> None:
    assert is_contact_actionable({}, "voice") == (False, "CONSENT_MISSING")


def test_channel_consent_must_be_explicit() -> None:
    contact: dict[str, object] = {"consent": True}

    assert is_contact_actionable(contact, "voice") == (
        False,
        "CONSENT_MISSING",
    )


def test_explicit_channel_consent_is_sufficient_without_generic_consent() -> None:
    assert is_contact_actionable({"consent_email": True}, "email") == (True, None)


def test_snake_case_do_not_contact_denies_model_dump_shape() -> None:
    assert is_contact_actionable(
        {"do_not_contact": True, "consent_email": True}, "email"
    ) == (False, "DO_NOT_CONTACT")


def test_camel_case_channel_consent_is_normalized() -> None:
    assert is_contact_actionable({"consentEmail": True}, "email") == (True, None)
