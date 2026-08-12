"""Safety regression tests for the operator-run backup/restore tooling."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
TOOL = REPOSITORY_ROOT / "tooling" / "backup_restore_evidence.py"


def _load_tool():
    spec = spec_from_file_location("backup_restore_evidence", TOOL)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_restore_target_refuses_the_source_database_even_with_different_urls() -> None:
    tool = _load_tool()

    with pytest.raises(ValueError, match="source database"):
        tool.validate_isolated_restore_target(
            source_url="postgresql://backup:secret@db.example/signalloop",
            target_url="postgresql://restore:secret@recovery.example/signalloop",
        )


def test_restore_target_requires_an_explicit_isolation_marker() -> None:
    tool = _load_tool()

    with pytest.raises(ValueError, match="isolation marker"):
        tool.validate_isolated_restore_target(
            source_url="postgresql://backup:secret@db.example/signalloop",
            target_url="postgresql://restore:secret@recovery.example/signalloop_candidate",
        )


def test_evidence_is_secret_free_and_hashes_the_backup(tmp_path: Path) -> None:
    tool = _load_tool()
    backup = tmp_path / "tenant.dump"
    backup.write_bytes(b"safe test backup")

    evidence = tool.build_evidence(
        backup=backup,
        source_url="postgresql://backup:top-secret@db.example/signalloop",
        target_url="postgresql://restore:another-secret@recovery.example/signalloop_restore",
        tool_versions={"pg_dump": "pg_dump (PostgreSQL) 16.4"},
        migration_head="phase1_head",
        row_validation={"workspace": 1, "audit_event": 4},
        created_at="2026-08-12T12:00:00+00:00",
    )

    serialized = tool.canonical_json(evidence)
    assert evidence["backup"]["sha256"]
    assert evidence["source_database"] == "signalloop"
    assert evidence["target_database"] == "signalloop_restore"
    assert "top-secret" not in serialized
    assert "another-secret" not in serialized
    assert "db.example" not in serialized
    assert evidence["row_validation"] == {"audit_event": 4, "workspace": 1}


def test_restore_plan_contains_no_credentials_and_requires_explicit_confirmation(
    tmp_path: Path,
) -> None:
    tool = _load_tool()
    backup = tmp_path / "tenant.dump"
    backup.write_bytes(b"safe test backup")

    plan = tool.build_restore_plan(
        backup=backup,
        target_url="postgresql://restore:secret@recovery.example/signalloop_restore",
    )

    assert "secret" not in plan["command"]
    assert "PGPASSWORD" not in plan["command"]
    assert plan["requires_confirmation"] is True
    assert "--clean" not in plan["command"]


def test_evidence_requires_a_nonempty_migration_head(tmp_path: Path) -> None:
    tool = _load_tool()
    backup = tmp_path / "tenant.dump"
    backup.write_bytes(b"safe test backup")

    with pytest.raises(ValueError, match="migration head"):
        tool.build_evidence(
            backup=backup,
            source_url="postgresql://backup:secret@db.example/signalloop",
            target_url="postgresql://restore:secret@recovery.example/signalloop_restore",
            tool_versions={"pg_dump": "pg_dump (PostgreSQL) 16.4"},
            migration_head="",
            row_validation={},
        )
