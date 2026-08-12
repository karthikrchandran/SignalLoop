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


def _uses_shared_filtered_table_helper(call: ast.Call) -> bool:
    """Return whether ``tables`` comes from the pgvector-aware shared helper."""
    tables_keyword = next(
        (keyword for keyword in call.keywords if keyword.arg == "tables"),
        None,
    )
    if tables_keyword is None or not isinstance(tables_keyword.value, ast.Call):
        return False
    return (
        isinstance(tables_keyword.value.func, ast.Name)
        and tables_keyword.value.func.id == "_metadata_tables_for_available_extensions"
    )


def _full_schema_creators(route_tests: Path) -> list[str]:
    """Find route tests that bypass the pgvector-aware root fixture."""
    creators: list[str] = []

    for route_test in route_tests.rglob("test_*.py"):
        tree = ast.parse(route_test.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "create_all":
                continue
            if not (
                isinstance(call.func.value, ast.Attribute)
                and call.func.value.attr == "metadata"
                and isinstance(call.func.value.value, ast.Name)
                and call.func.value.value.id == "SQLModel"
            ):
                continue
            if not _uses_shared_filtered_table_helper(call):
                creators.append(
                    f"{route_test.relative_to(route_tests).as_posix()}:{call.lineno}"
                )

    return creators


def test_schema_guard_rejects_explicit_none_tables(tmp_path: Path) -> None:
    route_test = tmp_path / "test_none_tables.py"
    route_test.write_text(
        "SQLModel.metadata.create_all(engine, tables=None)\n",
        encoding="utf-8",
    )

    assert _full_schema_creators(tmp_path) == ["test_none_tables.py:1"]


def test_schema_guard_rejects_sorted_metadata_tables(tmp_path: Path) -> None:
    route_test = tmp_path / "test_sorted_tables.py"
    route_test.write_text(
        "SQLModel.metadata.create_all(engine, tables=SQLModel.metadata.sorted_tables)\n",
        encoding="utf-8",
    )

    assert _full_schema_creators(tmp_path) == ["test_sorted_tables.py:1"]


def test_schema_guard_recurses_into_nested_route_test_modules(tmp_path: Path) -> None:
    nested_test = tmp_path / "nested" / "test_bypass.py"
    nested_test.parent.mkdir()
    nested_test.write_text("SQLModel.metadata.create_all(engine)\n", encoding="utf-8")

    assert _full_schema_creators(tmp_path) == ["nested/test_bypass.py:1"]


def test_schema_guard_allows_the_shared_filtered_table_helper(tmp_path: Path) -> None:
    route_test = tmp_path / "test_filtered_tables.py"
    route_test.write_text(
        "SQLModel.metadata.create_all(\n"
        "    engine,\n"
        "    tables=_metadata_tables_for_available_extensions(pgvector_available),\n"
        ")\n",
        encoding="utf-8",
    )

    assert _full_schema_creators(tmp_path) == []


def test_route_tests_do_not_create_the_full_metadata_schema() -> None:
    """Route tests must inherit the pgvector-aware root database fixture."""
    route_tests = Path(__file__).parents[1] / "api" / "routes"

    assert _full_schema_creators(route_tests) == []
