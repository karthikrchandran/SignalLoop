"""Domain service: ``mapping service``."""

from __future__ import annotations

from typing import Any

REQUIRED_FIELDS = ["email", "firstName", "company", "timezone"]


def resolve_mapping(headers: list[str], mapping: dict[str, str], *, strict: bool = False) -> dict[str, str]:
    """Resolve mapping."""
    resolved = {field: mapping.get(field, field) for field in REQUIRED_FIELDS}
    available = set(headers)

    if strict:
        missing_sources = [
            source
            for source in mapping.values()
            if source and source not in available
        ]
        if missing_sources:
            missing_unique = ", ".join(sorted(set(missing_sources)))
            raise ValueError(f"Mapping contains unknown source columns: {missing_unique}")

    for field, source in list(resolved.items()):
        if source not in available:
            resolved[field] = ""
    return resolved


def map_row(row: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Map row."""
    return {canonical: row.get(source, "") for canonical, source in mapping.items()}
