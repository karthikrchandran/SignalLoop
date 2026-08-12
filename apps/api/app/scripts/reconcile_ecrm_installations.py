"""One-shot per-stream eCRM installation reconciliation command."""

from __future__ import annotations

import argparse

from sqlmodel import Session

from app.core.db import engine
from app.domain.ecrm_installations.repository import EcrmInstallationRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile one eCRM installation stream")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--stream-key", required=True)
    parser.add_argument("--source-count", required=True, type=int)
    parser.add_argument("--source-checkpoint", required=True, type=int)
    args = parser.parse_args()
    with Session(engine) as session:
        repair = EcrmInstallationRepository(session).reconcile_stream(
            workspace_id=args.workspace_id,
            stream_key=args.stream_key,
            source_count=args.source_count,
            source_checkpoint=args.source_checkpoint,
        )
        session.commit()
        print({"matched": repair is None, "repair_id": str(repair.id) if repair else None})  # noqa: T201


if __name__ == "__main__":
    main()
