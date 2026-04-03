from __future__ import annotations

import csv
import io
from typing import Any

from app.domain.contacts.mapping_service import REQUIRED_FIELDS, map_row, resolve_mapping
from app.domain_models import ImportRowError, SemanticError


def parse_csv(file_bytes: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    decoded = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    headers = reader.fieldnames or []
    rows = [dict(row) for row in reader]
    return headers, rows


def validate_rows(headers: list[str], rows: list[dict[str, Any]], mapping: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[ImportRowError]]:
    effective_mapping = resolve_mapping(headers, mapping or {})
    valid_rows: list[dict[str, Any]] = []
    errors: list[ImportRowError] = []

    missing_required = [field for field, source in effective_mapping.items() if not source]
    if missing_required:
        for field in missing_required:
            errors.append(
                ImportRowError(
                    row_number=0,
                    column=field,
                    semantic_error=SemanticError.recipient_invalid,
                    message=f"Map a source column for {field} before final import.",
                )
            )
        return valid_rows, errors

    for index, row in enumerate(rows, start=1):
        mapped = map_row(row, effective_mapping)
        row_errors: list[ImportRowError] = []
        for field in REQUIRED_FIELDS:
            value = str(mapped.get(field, "")).strip()
            if not value:
                row_errors.append(
                    ImportRowError(
                        row_number=index,
                        column=field,
                        semantic_error=SemanticError.recipient_invalid,
                        message=f"{field} is required for import.",
                    )
                )
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append(mapped)
    return valid_rows, errors


def preview_rows(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    return rows[:limit]
