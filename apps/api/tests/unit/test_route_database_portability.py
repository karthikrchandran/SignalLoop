"""Guard route tests against bypassing the portable database fixture."""

import ast
from pathlib import Path

from sqlmodel import SQLModel

from tests.conftest import (
    _metadata_tables_for_available_extensions,
    _table_uses_pgvector,
)


def test_pgvector_fallback_excludes_only_vector_backed_tables() -> None:
    """The inherited route fixture can initialize a database without pgvector."""
    tables = _metadata_tables_for_available_extensions(pgvector_available=False)

    assert tables is not None
    assert tables
    assert len(tables) < len(SQLModel.metadata.sorted_tables)
    assert not any(_table_uses_pgvector(table) for table in tables)


def test_route_tests_do_not_create_the_full_metadata_schema() -> None:
    """Route tests must inherit the pgvector-aware root database fixture."""
    route_tests = Path(__file__).parents[1] / "api" / "routes"
    full_schema_creators: list[str] = []

    for route_test in route_tests.glob("test_*.py"):
        tree = ast.parse(route_test.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "create_all":
                continue
            if not any(keyword.arg == "tables" for keyword in call.keywords):
                full_schema_creators.append(route_test.name)

    assert full_schema_creators == []
