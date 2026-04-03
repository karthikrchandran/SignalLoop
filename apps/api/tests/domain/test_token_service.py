from app.domain.outreach.token_service import parse_tokens, render_template, validate_token_definitions


def test_parse_tokens_extracts_dot_notation_tokens() -> None:
    content = "Hello {{contact.firstName}} from {{contact.company}}"
    assert parse_tokens(content) == ["contact.firstName", "contact.company"]


def test_validate_token_definitions_rejects_duplicates_invalid_source_and_fallback() -> None:
    errors = validate_token_definitions(
        [
            {
                "name": "contact.firstName",
                "source_field": "contact.firstName",
                "default_value": "there",
                "fallback_behavior": "defaultValue",
            },
            {
                "name": "contact.firstName",
                "source_field": "contact.nickname",
                "default_value": None,
                "fallback_behavior": "invalidFallback",
            },
        ]
    )

    assert "Token contact.firstName must be unique." in errors
    assert "Token contact.firstName uses unsupported source field contact.nickname." in errors
    assert "Token contact.firstName uses unsupported fallback behavior invalidFallback." in errors


def test_render_template_uses_payload_then_default_then_unresolved_warning() -> None:
    content = "Hi {{contact.firstName}} from {{contact.company}} in {{contact.timezone}}"
    rendered, unresolved = render_template(
        content,
        {
            "contact": {
                "firstName": "Asha",
            }
        },
        [
            {
                "name": "contact.company",
                "source_field": "contact.company",
                "default_value": "Contoso",
                "fallback_behavior": "defaultValue",
            },
            {
                "name": "contact.timezone",
                "source_field": "contact.timezone",
                "default_value": None,
                "fallback_behavior": "unresolvedWarning",
            },
        ],
    )

    assert rendered == "Hi Asha from Contoso in [contact.timezone]"
    assert unresolved == ["contact.timezone"]
