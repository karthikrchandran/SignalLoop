from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager

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
            account = repo.upsert_account(
                workspace_id=workspace_id,
                external_key=str(
                    record.get("externalKey")
                    or f"ecrm:customer:{workspace_id}:{record.get('id')}"
                ),
                display_name=str(record.get("displayName") or record.get("companyName") or ""),
                source_app="ecrm",
                source_record_id=str(record.get("id") or ""),
            )
            imported_accounts[str(record.get("id") or "")] = account.id
            summary["accounts"] += 1

        for record in fetch_records("CONTACT"):
            parent_account_id = imported_accounts.get(str(record.get("parentId") or ""))
            repo.upsert_contact(
                workspace_id=workspace_id,
                external_key=str(
                    record.get("externalKey")
                    or f"ecrm:contact:{workspace_id}:{record.get('id')}"
                ),
                display_name=str(record.get("displayName") or record.get("email") or ""),
                email=str(record.get("email") or ""),
                parent_account_id=parent_account_id,
                source_app="ecrm",
                source_record_id=str(record.get("id") or ""),
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
