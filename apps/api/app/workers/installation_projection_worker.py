"""One-shot durable eCRM installation projection worker command."""

from __future__ import annotations

import argparse

from sqlmodel import Session

from app.core.db import engine
from app.domain.ecrm_installations.repository import EcrmInstallationRepository
from app.domain.ecrm_installations.service import InstallationProjectionWorker


def run(*, workspace_id: str | None = None, limit: int = 100) -> dict[str, int]:
    with Session(engine) as session:
        return InstallationProjectionWorker(EcrmInstallationRepository(session)).run_once(
            workspace_id=workspace_id, limit=limit
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process durable eCRM installation projections once")
    parser.add_argument("--workspace-id")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    print(run(workspace_id=args.workspace_id, limit=args.limit))  # noqa: T201


if __name__ == "__main__":
    main()
