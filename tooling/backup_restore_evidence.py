"""Prepare secret-free evidence for an isolated PostgreSQL restore rehearsal.

This tool deliberately does not invoke ``pg_restore``.  It validates the
operator's isolated target, captures preflight evidence, and emits the one
manual restore command that an approved operator may run after review.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ISOLATION_MARKERS = ("_restore", "_recovery", "_isolated")
ROW_VALIDATION_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,62}$")


def database_name(connection_url: str) -> str:
    """Return the PostgreSQL database name without exposing connection details."""
    parsed = urlparse(connection_url)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.path.strip("/"):
        raise ValueError("connection URL must name a PostgreSQL database")
    return unquote(parsed.path.strip("/").split("/", maxsplit=1)[0])


def validate_isolated_restore_target(source_url: str, target_url: str) -> tuple[str, str]:
    """Reject a target that could be the active/source database."""
    source_database = database_name(source_url)
    target_database = database_name(target_url)
    if source_database.casefold() == target_database.casefold():
        raise ValueError("restore target must not be the source database")
    if not any(marker in target_database.casefold() for marker in ISOLATION_MARKERS):
        raise ValueError(
            "restore target database requires an isolation marker: "
            + ", ".join(ISOLATION_MARKERS)
        )
    return source_database, target_database


def sha256_file(path: Path) -> str:
    """Return the content hash for a backup artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: dict[str, Any]) -> str:
    """Serialize evidence deterministically for signing or archival."""
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def powershell_literal(value: str) -> str:
    """Quote a value as a PowerShell single-quoted literal."""
    return "'" + value.replace("'", "''") + "'"


def build_evidence(
    *,
    backup: Path,
    source_url: str,
    target_url: str,
    tool_versions: dict[str, str],
    migration_head: str,
    row_validation: dict[str, int],
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create portable evidence that never contains URLs, hosts, or credentials."""
    if not backup.is_file():
        raise ValueError("backup artifact does not exist")
    if not migration_head.strip():
        raise ValueError("migration head is required")
    source_database, target_database = validate_isolated_restore_target(source_url, target_url)
    if any(not ROW_VALIDATION_KEY.fullmatch(key) for key in row_validation):
        raise ValueError("row validation key must be a safe table identifier")
    if any(not isinstance(count, int) or count < 0 for count in row_validation.values()):
        raise ValueError("row validation counts must be non-negative integers")
    return {
        "schema_version": 1,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "backup": {
            "bytes": backup.stat().st_size,
            "sha256": sha256_file(backup),
        },
        "source_database": source_database,
        "target_database": target_database,
        "tool_versions": dict(sorted(tool_versions.items())),
        "migration_head": migration_head,
        "row_validation": dict(sorted(row_validation.items())),
        "restore_execution": "not-run-by-tool",
    }


def build_restore_plan(*, backup: Path, target_url: str) -> dict[str, Any]:
    """Return a credential-free command for an operator-approved restore."""
    target_database = database_name(target_url)
    if not any(marker in target_database.casefold() for marker in ISOLATION_MARKERS):
        raise ValueError("restore target database requires an isolation marker")
    return {
        "target_database": target_database,
        "requires_confirmation": True,
        "command": (
            "pg_restore --exit-on-error --no-owner --no-privileges "
            '--dbname "$env:RECOVERY_DATABASE_URL" '
            + powershell_literal(str(backup))
        ),
        "safety_notes": [
            "Run only after confirming RECOVERY_DATABASE_URL points to the isolated target.",
            "The command intentionally omits --clean and never targets the source database.",
        ],
    }


def executable_version(executable: str) -> str:
    """Validate a required PostgreSQL client tool and return its version line."""
    resolved = shutil.which(executable)
    if not resolved:
        raise ValueError(f"required PostgreSQL tool is unavailable: {executable}")
    result = subprocess.run(
        [resolved, "--version"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip() or result.stderr.strip()


def _read_row_validation(path: Path | None) -> dict[str, int]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("row validation file must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--source-url-env", default="DATABASE_URL")
    parser.add_argument("--target-url-env", default="RECOVERY_DATABASE_URL")
    parser.add_argument("--migration-head", required=True)
    parser.add_argument("--row-validation", type=Path)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--emit-restore-plan", action="store_true")
    args = parser.parse_args()

    import os

    source_url = os.environ.get(args.source_url_env)
    target_url = os.environ.get(args.target_url_env)
    if not source_url or not target_url:
        raise SystemExit("source and recovery URLs must be provided through environment variables")
    try:
        versions = {name: executable_version(name) for name in ("pg_dump", "pg_restore")}
        evidence = build_evidence(
            backup=args.backup,
            source_url=source_url,
            target_url=target_url,
            tool_versions=versions,
            migration_head=args.migration_head,
            row_validation=_read_row_validation(args.row_validation),
        )
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(canonical_json(evidence), encoding="utf-8")
        if args.emit_restore_plan:
            print(  # noqa: T201 - command-line tool intentionally emits the reviewed plan.
                canonical_json(build_restore_plan(backup=args.backup, target_url=target_url))
            )
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
