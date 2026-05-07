"""Domain service: ``token service``."""

from __future__ import annotations

import re
from typing import Any

TOKEN_PATTERN = re.compile(r"{{\s*([\w.]+)\s*}}")
VALID_FALLBACK_BEHAVIORS = {"defaultValue", "unresolvedWarning"}

ALLOWED_SOURCE_FIELDS = {
    "contact.firstName",
    "contact.company",
    "contact.timezone",
    "contact.email",
}


def parse_tokens(content: str) -> list[str]:
    """Parse tokens."""
    return TOKEN_PATTERN.findall(content)


def validate_token_definitions(tokens: list[dict[str, Any]]) -> list[str]:
    """Validate token definitions."""
    errors: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        name = token["name"]
        source_field = token["source_field"]
        fallback_behavior = token.get("fallback_behavior", "defaultValue")

        if name in seen:
            errors.append(f"Token {name} must be unique.")
        seen.add(name)

        if source_field not in ALLOWED_SOURCE_FIELDS:
            errors.append(f"Token {name} uses unsupported source field {source_field}.")

        if fallback_behavior not in VALID_FALLBACK_BEHAVIORS:
            errors.append(
                f"Token {name} uses unsupported fallback behavior {fallback_behavior}."
            )

    return errors


def render_template(content: str, sample_payload: dict[str, Any], tokens: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """Render template."""
    unresolved: list[str] = []

    token_index = {token["source_field"]: token for token in tokens}

    def replacer(match: re.Match[str]) -> str:
        """Replacer."""
        key = match.group(1)
        value: Any = sample_payload
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                value = None
                break

        if value not in (None, ""):
            return str(value)

        token_def = token_index.get(key, {})
        default_value = token_def.get("default_value")
        fallback_behavior = token_def.get("fallback_behavior", "defaultValue")

        if default_value not in (None, ""):
            return str(default_value)

        if fallback_behavior in VALID_FALLBACK_BEHAVIORS:
            unresolved.append(key)

        return f"[{key}]"

    return TOKEN_PATTERN.sub(replacer, content), unresolved
