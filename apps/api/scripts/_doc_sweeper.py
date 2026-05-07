"""Bulk docstring sweeper for ``apps/api/app``.

Adds docstrings to:
  * modules that lack a top-level docstring,
  * public classes / functions / async functions without a docstring,

deriving wording from naming conventions (CamelCase splits, ``__tablename__``,
common verb prefixes such as ``get_``/``list_``/``create_``).

It is intentionally **conservative**:
  * Never edits a node that already has a docstring.
  * Never touches private symbols (leading underscore).
  * Never touches __init__ method bodies.
  * Preserves all existing whitespace and code; only inserts new docstring lines.

Run with ``python scripts/_doc_sweeper.py`` from ``apps/api``. Idempotent —
re-running on already-documented code is a no-op.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1] / "app"

# Files we deliberately skip — they're already curated or tooling-owned.
SKIP_RELATIVE = {
    "alembic/env.py",
}

# Verb prefixes used by service/route methods → human-readable descriptions.
VERB_PHRASES: dict[str, str] = {
    "get_": "Return",
    "list_": "Return a list of",
    "fetch_": "Return",
    "read_": "Return",
    "create_": "Create",
    "update_": "Update",
    "delete_": "Delete",
    "remove_": "Remove",
    "add_": "Add",
    "set_": "Set",
    "make_": "Create",
    "send_": "Send",
    "verify_": "Verify",
    "validate_": "Validate",
    "render_": "Render",
    "parse_": "Parse",
    "preview_": "Build a preview of",
    "publish_": "Publish",
    "clone_": "Clone",
    "pause_": "Pause",
    "resume_": "Resume",
    "enroll_": "Enroll",
    "enqueue_": "Enqueue",
    "handle_": "Handle",
    "init": "Initialise",
    "register_": "Register",
    "dispatch": "Dispatch the incoming request",
    "main": "Entry point",
    "lifespan": "FastAPI lifespan context manager",
    "ping": "Ping",
    "connect": "Open a connection",
    "disconnect": "Close the connection",
    "upgrade": "Apply this Alembic migration",
    "downgrade": "Revert this Alembic migration",
    "matches_": "Return ``True`` if",
    "estimate_": "Estimate",
    "transition_": "Transition",
    "apply_": "Apply",
    "evaluate_": "Evaluate",
    "check_": "Check",
    "is_": "Return ``True`` when",
    "require_": "Validate and return",
    "resolve_": "Resolve",
    "map_": "Map",
    "normalize_": "Normalise",
    "deactivate_": "Deactivate",
    "download_": "Download",
    "import_": "Import",
    "persist_": "Persist",
    "assign_": "Assign",
    "flag_": "Flag",
    "start_": "Start",
    "close_": "Close",
}


def _split_camel(name: str) -> str:
    """Split ``CamelCaseName`` into ``camel case name``."""
    spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name).lower()
    return spaced


def _humanise_func(name: str) -> str:
    """Return a one-line docstring for a function named ``name``."""
    lower = name.lower()
    for prefix, phrase in VERB_PHRASES.items():
        if lower == prefix.rstrip("_") or lower.startswith(prefix):
            tail = lower[len(prefix):].replace("_", " ").strip()
            if not tail:
                return f"{phrase}."
            return f"{phrase} {tail}."
    # Fallback: e.g. "token_density" -> "Token density."
    return name.replace("_", " ").capitalize() + "."


def _humanise_class(name: str) -> str:
    """Return a one-line docstring for a class named ``name``."""
    pretty = _split_camel(name)
    suffix_map = [
        ("Service", f"Service for {pretty.removesuffix(' service')}."),
        ("Engine", f"{pretty.capitalize()}."),
        ("Manager", f"{pretty.capitalize()}."),
        ("Worker", f"Background worker: {pretty.removesuffix(' worker')}."),
        ("Status", f"Enumeration of {pretty.removesuffix(' status')} states."),
        ("Type", f"Enumeration of {pretty.removesuffix(' type')} variants."),
        ("Operator", f"Enumeration of {pretty.removesuffix(' operator')} comparison operators."),
        ("State", f"Enumeration of {pretty.removesuffix(' state')} states."),
        ("Provider", f"Enumeration of {pretty.removesuffix(' provider')} providers."),
        ("Error", f"Enumeration of {pretty.removesuffix(' error')} categories."),
        ("Outcome", f"Enumeration of {pretty.removesuffix(' outcome')} outcomes."),
        ("Create", f"Request payload for creating {pretty.removesuffix(' create')}."),
        ("Update", f"Request payload for updating {pretty.removesuffix(' update')}."),
        ("Request", f"Request payload: {pretty.removesuffix(' request')}."),
        ("Public", f"API response model: {pretty.removesuffix(' public')}."),
        ("Detail", f"Detail view of {pretty.removesuffix(' detail')}."),
        ("Item", f"List item: {pretty.removesuffix(' item')}."),
        ("Input", f"Input payload: {pretty.removesuffix(' input')}."),
        ("Definition", f"Definition: {pretty.removesuffix(' definition')}."),
        ("Violation", f"{pretty.capitalize()}."),
        ("Snapshot", f"Snapshot row: {pretty.removesuffix(' snapshot')}."),
        ("History", f"History row: {pretty.removesuffix(' history')}."),
        ("Event", f"Event row: {pretty.removesuffix(' event')}."),
        ("Decision", f"Decision row: {pretty.removesuffix(' decision')}."),
        ("Log", f"Log row: {pretty.removesuffix(' log')}."),
        ("Queue", f"Queue row: {pretty.removesuffix(' queue')}."),
        ("Stage", f"Staging row: {pretty.removesuffix(' stage')}."),
        ("Binding", f"Binding row: {pretty.removesuffix(' binding')}."),
        ("Policy", f"Policy row: {pretty.removesuffix(' policy')}."),
        ("Strategy", f"Strategy row: {pretty.removesuffix(' strategy')}."),
        ("Rule", f"Rule row: {pretty.removesuffix(' rule')}."),
        ("Token", f"Token row: {pretty.removesuffix(' token')}."),
        ("Version", f"Version row: {pretty.removesuffix(' version')}."),
        ("Pack", f"{pretty.capitalize()}."),
        ("Pair", f"{pretty.capitalize()}."),
        ("Result", f"Result row: {pretty.removesuffix(' result')}."),
        ("Summary", f"Summary row: {pretty.removesuffix(' summary')}."),
        ("Suppression", f"Suppression row: {pretty.removesuffix(' suppression')}."),
        ("Data", f"Data container: {pretty.removesuffix(' data')}."),
        ("Settings", f"Application settings."),
        ("Session", f"Session row: {pretty.removesuffix(' session')}."),
        ("Script", f"Script row: {pretty.removesuffix(' script')}."),
    ]
    for suffix, doc in suffix_map:
        if name.endswith(suffix):
            return doc
    return pretty.capitalize() + "."


def _module_doc(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if parts[0] == "alembic" and "versions" in parts:
        return "Alembic migration revision."
    if parts[-1] == "__init__.py":
        pkg = "/".join(parts[:-1]) or "app"
        return f"Package: ``{pkg}``."
    name = parts[-1].removesuffix(".py")
    pretty = name.replace("_", " ")
    parent = parts[-2] if len(parts) > 1 else ""
    if parent == "routes":
        return f"FastAPI router: ``{name}`` endpoints."
    if parent == "workers":
        return f"Background worker: ``{name}``."
    if parent == "providers":
        return f"External provider adapter: ``{name}``."
    if parent in {"services", "domain"} or name.endswith("_service"):
        return f"Domain service: ``{pretty}``."
    if name.endswith("_models") or name == "models":
        return f"Persistence + API models for the ``{parent or 'app'}`` domain."
    if name.endswith("_schemas") or name == "schemas":
        return f"Request/response schemas for the ``{parent or 'app'}`` domain."
    return f"Module: ``{pretty}``."


@dataclass
class Insertion:
    line: int  # 1-based; insert *before* this line
    text: str  # full lines to insert (each ends with \n)


def _detect_indent(lines: list[str], body_start_line: int) -> str:
    """Return the leading-whitespace string of the first non-blank body line."""
    for i in range(body_start_line - 1, len(lines)):
        stripped = lines[i].rstrip("\n")
        if stripped.strip():
            return stripped[: len(stripped) - len(stripped.lstrip())]
    return "    "


def _body_start_line(node: ast.AST) -> int:
    """Return the 1-based line number of the first statement of ``node``'s body."""
    body = getattr(node, "body", None)
    if not body:
        return getattr(node, "lineno", 1) + 1
    return body[0].lineno


def _has_docstring(node: ast.AST) -> bool:
    return ast.get_docstring(node) is not None


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _is_overload(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "overload":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "overload":
            return True
    return False


def _make_docstring_block(indent: str, text: str) -> str:
    return f'{indent}"""{text}"""\n'


def plan_insertions(source: str, rel: str) -> list[Insertion]:
    """Return all docstring insertions needed for ``source`` (sorted desc by line)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.splitlines(keepends=True)
    inserts: list[Insertion] = []

    # Module-level docstring
    if not _has_docstring(tree):
        # Find insertion line: after any leading comments/__future__ imports.
        # Simplest: insert at very top, before line 1.
        # But we must skip a leading shebang or coding header.
        text = _module_doc(rel)
        block = f'"""{text}"""\n\n'
        first_line = lines[0] if lines else ""
        # If first line is a future import or shebang, slot doc *before* it (Python allows).
        inserts.append(Insertion(line=1, text=block))

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not _is_public(node.name):
                continue
            if _is_overload(node):
                continue
            if _has_docstring(node):
                continue
            body_line = _body_start_line(node)
            indent = _detect_indent(lines, body_line)
            doc = _humanise_func(node.name)
            inserts.append(Insertion(line=body_line, text=_make_docstring_block(indent, doc)))
        elif isinstance(node, ast.ClassDef):
            if not _is_public(node.name):
                continue
            if _has_docstring(node):
                continue
            body_line = _body_start_line(node)
            indent = _detect_indent(lines, body_line)
            doc = _humanise_class(node.name)
            inserts.append(Insertion(line=body_line, text=_make_docstring_block(indent, doc)))

    # Sort descending so insertions don't shift later line numbers.
    inserts.sort(key=lambda ins: ins.line, reverse=True)
    return inserts


def apply_insertions(source: str, inserts: Iterable[Insertion]) -> str:
    lines = source.splitlines(keepends=True)
    for ins in inserts:
        idx = max(0, ins.line - 1)
        lines.insert(idx, ins.text)
    return "".join(lines)


def _iter_targets() -> Iterable[Path]:
    for py in ROOT.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(ROOT).as_posix()
        if rel in SKIP_RELATIVE:
            continue
        yield py


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    changed = 0
    for py in _iter_targets():
        rel = py.relative_to(ROOT).as_posix()
        src = py.read_text(encoding="utf-8")
        inserts = plan_insertions(src, rel)
        if not inserts:
            continue
        new_src = apply_insertions(src, inserts)
        if new_src == src:
            continue
        # Sanity-check: must still parse.
        try:
            ast.parse(new_src)
        except SyntaxError as exc:  # pragma: no cover - defensive
            print(f"[skip] {rel}: would break parse ({exc})", file=sys.stderr)
            continue
        if not dry:
            py.write_text(new_src, encoding="utf-8", newline="\n")
        changed += 1
        print(f"[{'dry' if dry else 'fix'}] {rel}: +{len(inserts)} docstrings")
    print(f"\n{changed} file(s) {'would be ' if dry else ''}updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
