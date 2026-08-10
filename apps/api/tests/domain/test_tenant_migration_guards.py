from __future__ import annotations

import importlib
from typing import Any

import pytest


migration = importlib.import_module(
    "app.alembic.versions.tenant_20260809_close_workspace_isolation"
)


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _Connection:
    def __init__(self, count: int) -> None:
        self.count = count
        self.statements: list[str] = []

    def execute(self, statement: Any) -> _ScalarResult:
        self.statements.append(str(statement))
        return _ScalarResult(self.count)


def test_migration_preflight_rejects_inconsistent_source_chain() -> None:
    connection = _Connection(count=1)

    with pytest.raises(RuntimeError, match="inconsistent call request ownership"):
        migration._preflight_or_raise(  # type: ignore[attr-defined]
            connection,
            "inconsistent call request ownership",
            "SELECT count(*) FROM call_requests",
        )


def test_migration_preflight_allows_clean_source_chain() -> None:
    connection = _Connection(count=0)

    migration._preflight_or_raise(  # type: ignore[attr-defined]
        connection,
        "clean",
        "SELECT count(*) FROM call_requests WHERE false",
    )

    assert connection.statements == ["SELECT count(*) FROM call_requests WHERE false"]
