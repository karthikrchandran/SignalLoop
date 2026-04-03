from __future__ import annotations

from typing import Any

from app.domain_models import SegmentOperator


def matches_rule(value: Any, operator: SegmentOperator, expected: str) -> bool:
    candidate = str(value or "")
    if operator == SegmentOperator.equals:
        return candidate == expected
    if operator == SegmentOperator.contains:
        return expected.lower() in candidate.lower()
    if operator == SegmentOperator.in_list:
        return candidate in [item.strip() for item in expected.split(",") if item.strip()]
    if operator == SegmentOperator.starts_with:
        return candidate.lower().startswith(expected.lower())
    return False


def estimate_segment(rows: list[dict[str, Any]], rules: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if all(matches_rule(row.get(rule["field_name"]), rule["operator"], rule["value"]) for rule in rules):
            count += 1
    return count
