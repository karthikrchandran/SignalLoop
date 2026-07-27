from __future__ import annotations

from typing import Any

from app.domain.shared_records.repository import PlatformSharedRepository
from app.integrations import ecrm_shared_records

_ENTITY_TYPES = ("CUSTOMER", "CONTACT", "LEAD", "ORDER")
_PAGE_SIZE = 500


def reconcile_counts(
    *,
    ecrm_counts: dict[str, int],
    local_counts: dict[str, int],
) -> dict[str, object]:
    normalized_ecrm_counts = {
        entity_type: int(ecrm_counts.get(entity_type, 0))
        for entity_type in _ENTITY_TYPES
    }
    normalized_local_counts = {
        entity_type: int(local_counts.get(entity_type, 0))
        for entity_type in _ENTITY_TYPES
    }
    diffs: list[dict[str, int | str]] = []

    for entity_type in _ENTITY_TYPES:
        expected = normalized_ecrm_counts[entity_type]
        actual = normalized_local_counts[entity_type]
        if expected != actual:
            diffs.append(
                {
                    "entity": entity_type,
                    "expected": expected,
                    "actual": actual,
                }
            )

    return {
        "status": "ok" if not diffs else "mismatch",
        "diffs": diffs,
        "ecrm_counts": normalized_ecrm_counts,
        "local_counts": normalized_local_counts,
    }


def build_reconciliation_report(
    *,
    repo: PlatformSharedRepository,
    workspace_id: str,
) -> dict[str, object]:
    ecrm_counts = count_ecrm_export_records(workspace_id=workspace_id)
    local_counts = count_local_records(repo=repo, workspace_id=workspace_id)
    return reconcile_counts(ecrm_counts=ecrm_counts, local_counts=local_counts)


def count_local_records(
    *,
    repo: PlatformSharedRepository,
    workspace_id: str,
) -> dict[str, int]:
    return {
        "CUSTOMER": repo.count_active_accounts(workspace_id=workspace_id),
        "CONTACT": repo.count_active_contacts(workspace_id=workspace_id),
        "LEAD": repo.count_active_identities(
            workspace_id=workspace_id,
            entity_type="LEAD",
        ),
        "ORDER": repo.count_active_identities(
            workspace_id=workspace_id,
            entity_type="ORDER",
        ),
    }


def count_ecrm_export_records(*, workspace_id: str) -> dict[str, int]:
    counts = {entity_type: 0 for entity_type in _ENTITY_TYPES}

    for entity_type in _ENTITY_TYPES:
        cursor: str | None = None
        while True:
            response = ecrm_shared_records.list_shared_records_export_page(
                entity_type=entity_type,
                cursor=cursor,
                limit=_PAGE_SIZE,
            )
            for record in _page_records(response):
                if _is_active_record(record) and _record_workspace_id(record) == workspace_id:
                    counts[entity_type] += 1

            cursor = _next_cursor(response)
            if cursor is None:
                break

    return counts


def _page_records(response: dict[str, object]) -> list[dict[str, Any]]:
    items = response.get("items", response.get("records", []))
    if not isinstance(items, list):
        return []
    return [record for record in items if isinstance(record, dict)]


def _record_workspace_id(record: dict[str, object]) -> str | None:
    data = record.get("data")
    if isinstance(data, dict):
        workspace_id = _string_value(data.get("workspaceId"))
        if workspace_id is not None:
            return workspace_id
    return _string_value(record.get("workspaceId"))


def _is_active_record(record: dict[str, object]) -> bool:
    status = _string_value(record.get("status"))
    return status is None or status.lower() == "active"


def _next_cursor(response: dict[str, object]) -> str | None:
    return _string_value(response.get("nextCursor"))


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
