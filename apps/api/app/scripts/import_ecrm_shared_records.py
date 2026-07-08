from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from sqlmodel import Session

from app.core.db import engine
from app.domain.shared_records.repository import PlatformSharedRepository
from app.integrations import ecrm_shared_records


@contextmanager
def _session_scope(session: Session | None = None) -> Iterator[Session]:
    managed_session = session or Session(engine)
    owns_session = session is None
    try:
        yield managed_session
    finally:
        if owns_session:
            managed_session.close()


def fetch_records(
    entity_type: str,
    *,
    parent_id: str | None = None,
) -> list[dict[str, object]]:
    response = ecrm_shared_records.list_shared_records(
        entity_type=entity_type,
        parent_id=parent_id,
        status="active",
        limit=500,
    )
    records = response.get("records", response.get("items", []))
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def _record_workspace_id(record: dict[str, object]) -> str | None:
    data = record.get("data")
    if isinstance(data, dict):
        workspace_id = data.get("workspaceId")
        if isinstance(workspace_id, str) and workspace_id.strip():
            return workspace_id.strip()
    workspace_id = record.get("workspaceId")
    if isinstance(workspace_id, str) and workspace_id.strip():
        return workspace_id.strip()
    return None


def _record_data(record: dict[str, object]) -> dict[str, object]:
    data = record.get("data")
    return data if isinstance(data, dict) else {}


def _timestamp(record: dict[str, object], *keys: str) -> datetime | None:
    for key in keys:
        raw_value = record.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                return datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def run_import(
    *,
    workspace_id: str,
    dry_run: bool = True,
    session: Session | None = None,
) -> dict[str, object]:
    summary = {
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "accounts": 0,
        "contacts": 0,
    }

    with _session_scope(session) as active_session:
        repo = PlatformSharedRepository(active_session)
        imported_accounts: dict[str, object] = {}

        for record in fetch_records("CUSTOMER"):
            if _record_workspace_id(record) != workspace_id:
                continue
            data = _record_data(record)
            account = repo.upsert_account(
                workspace_id=workspace_id,
                external_key=str(
                    record.get("externalKey")
                    or f"ecrm:customer:{workspace_id}:{record.get('id')}"
                ),
                display_name=str(record.get("displayName") or record.get("companyName") or ""),
                status=str(record.get("status") or "active"),
                account_key=(
                    str(data.get("accountKey")) if data.get("accountKey") is not None else None
                ),
                website_url=(
                    str(data.get("websiteUrl")) if data.get("websiteUrl") is not None else None
                ),
                industry=(
                    str(data.get("industry")) if data.get("industry") is not None else None
                ),
                summary=(
                    str(data.get("summary")) if data.get("summary") is not None else None
                ),
                tags=[tag for tag in data.get("tags", []) if isinstance(tag, str)]
                if isinstance(data.get("tags"), list)
                else [],
                created_at=_timestamp(record, "createdAt", "created_at"),
                updated_at=_timestamp(record, "updatedAt", "updated_at", "createdAt", "created_at"),
                source_app="ecrm",
                source_record_id=str(record.get("id") or ""),
            )
            legacy_id = record.get("emailVoiceLegacyId") or record.get(
                "email_voice_legacy_id"
            )
            if isinstance(legacy_id, str) and legacy_id.strip():
                repo.upsert_source_link(
                    workspace_id=workspace_id,
                    entity_type="ACCOUNT",
                    entity_id=account.id,
                    source_app="emailvoice",
                    source_record_id=legacy_id.strip(),
                )
            imported_accounts[str(record.get("id") or "")] = account.id
            summary["accounts"] += 1

        for record in fetch_records("CONTACT"):
            if _record_workspace_id(record) != workspace_id:
                continue
            data = _record_data(record)
            parent_account_id = imported_accounts.get(str(record.get("parentId") or ""))
            contact = repo.upsert_contact(
                workspace_id=workspace_id,
                external_key=str(
                    record.get("externalKey")
                    or f"ecrm:contact:{workspace_id}:{record.get('id')}"
                ),
                display_name=str(record.get("displayName") or record.get("email") or ""),
                email=str(record.get("email") or ""),
                phone=(
                    str(record.get("phone")) if record.get("phone") is not None else None
                ),
                company_name=(
                    str(record.get("companyName")) if record.get("companyName") is not None else None
                ),
                first_name=(
                    str(data.get("firstName")) if data.get("firstName") is not None else None
                ),
                last_name=(
                    str(data.get("lastName")) if data.get("lastName") is not None else None
                ),
                timezone=str(data.get("timezone") or "UTC"),
                source_channel=(
                    str(data.get("sourceChannel")) if data.get("sourceChannel") is not None else None
                ),
                tags=[tag for tag in data.get("tags", []) if isinstance(tag, str)]
                if isinstance(data.get("tags"), list)
                else [],
                intents=[intent for intent in data.get("intents", []) if isinstance(intent, str)]
                if isinstance(data.get("intents"), list)
                else [],
                last_seen_at=_timestamp(data, "lastSeenAt", "last_seen_at"),
                status=str(record.get("status") or "active"),
                created_at=_timestamp(record, "createdAt", "created_at"),
                updated_at=_timestamp(record, "updatedAt", "updated_at", "createdAt", "created_at"),
                parent_account_id=parent_account_id,
                source_app="ecrm",
                source_record_id=str(record.get("id") or ""),
            )
            legacy_id = record.get("emailVoiceLegacyId") or record.get(
                "email_voice_legacy_id"
            )
            if isinstance(legacy_id, str) and legacy_id.strip():
                repo.upsert_source_link(
                    workspace_id=workspace_id,
                    entity_type="CONTACT",
                    entity_id=contact.id,
                    source_app="emailvoice",
                    source_record_id=legacy_id.strip(),
                )
            summary["contacts"] += 1

        if dry_run:
            active_session.rollback()
        else:
            active_session.commit()

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = run_import(workspace_id=args.workspace_id, dry_run=args.dry_run)
    sys.stdout.write(f"{json.dumps(summary)}\n")


if __name__ == "__main__":
    main()
