"""Regression tests for the checked-in frontend OpenAPI input."""

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EXPORT_SCRIPT = REPOSITORY_ROOT / "tooling" / "export_openapi.py"


def _load_export_module():
    spec = spec_from_file_location("export_openapi", EXPORT_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_export_openapi_writes_the_application_schema_without_a_running_server(
    tmp_path: Path,
) -> None:
    exporter = _load_export_module()
    output = tmp_path / "openapi.json"

    exporter.export_openapi_spec(output)

    schema = json.loads(output.read_text(encoding="utf-8"))
    assert schema["openapi"].startswith("3.")
    assert "/api/v1/utils/health-check/" in schema["paths"]


def test_openapi_input_matches_the_current_application_schema() -> None:
    exporter = _load_export_module()

    assert exporter.openapi_input_is_current(
        REPOSITORY_ROOT / "apps" / "web" / "openapi.json"
    )
