from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def test_nullable_signal_downgrade_rejects_rows_without_signal_events(
    monkeypatch,
) -> None:
    path = (
        Path(__file__).parents[2]
        / "app"
        / "alembic"
        / "versions"
        / "p1_calendar_intent_nullable_20260816.py"
    )
    spec = importlib.util.spec_from_file_location("calendar_intent_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class Result:
        def scalar_one(self) -> int:
            return 1

    class Bind:
        def execute(self, _statement):
            return Result()

    monkeypatch.setattr(migration.op, "get_bind", lambda: Bind())
    with pytest.raises(RuntimeError, match="signal_event_id"):
        migration.downgrade()
