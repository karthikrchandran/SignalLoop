"""One-shot inventory script: find Python files in app/ that lack docstrings.

Reports, per file under ``app/``:
  - whether the module has a top-level docstring
  - count of public classes / functions missing docstrings
  - list of public symbol names missing docstrings (first 10)

Output is plain text on stdout, sorted by total missing count desc.
This script has no external deps; safe to run from venv.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def inspect(path: Path) -> tuple[bool, int, list[str]]:
    """Return ``(has_module_doc, missing_count, missing_names)`` for ``path``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return (True, 0, [])  # skip unparsable
    has_module_doc = ast.get_docstring(tree) is not None
    missing: list[str] = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and _is_public(node.name):
            if ast.get_docstring(node) is None:
                missing.append(node.name)
    return (has_module_doc, len(missing), missing)


def main() -> None:
    rows: list[tuple[Path, bool, int, list[str]]] = []
    for py in ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        has_doc, miss, names = inspect(py)
        if has_doc and miss == 0:
            continue
        rows.append((py, has_doc, miss, names))
    rows.sort(key=lambda r: (-r[2], r[0].as_posix()))
    print(f"files needing attention: {len(rows)}")
    for path, has_doc, miss, names in rows:
        rel = path.relative_to(ROOT.parent).as_posix()
        flag = "" if has_doc else " [no module doc]"
        sample = ", ".join(names[:8]) + (" ..." if len(names) > 8 else "")
        print(f"{miss:>3}  {rel}{flag}  -> {sample}")


if __name__ == "__main__":
    main()
