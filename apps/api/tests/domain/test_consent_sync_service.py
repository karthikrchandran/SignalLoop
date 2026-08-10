from app.domain.policies.consent_sync_service import is_contact_actionable


def test_missing_consent_is_not_actionable() -> None:
    assert is_contact_actionable({}, "voice") == (False, "CONSENT_MISSING")


def test_channel_consent_must_be_explicit() -> None:
    contact: dict[str, object] = {"consent": True}

    assert is_contact_actionable(contact, "voice") == (
        False,
        "CONSENT_MISSING",
    )
