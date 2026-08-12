"""Export the FastAPI schema used to generate the checked-in web client."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "apps" / "api"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "apps" / "web" / "openapi.json"

# Schema export never opens a database connection, but importing the FastAPI
# application still validates these required runtime settings.  Supply only
# non-secret, export-only defaults so contributors and CI do not need a local
# service stack just to regenerate the typed client input.
EXPORT_DEFAULTS = {
    "PROJECT_NAME": "SignalLoop",
    "POSTGRES_SERVER": "localhost",
    "POSTGRES_USER": "openapi_export",
    "POSTGRES_DB": "signalloop",
    "FIRST_SUPERUSER": "openapi-export@example.com",
    "FIRST_SUPERUSER_PASSWORD": "openapi-export-only",
}

for name, value in EXPORT_DEFAULTS.items():
    os.environ.setdefault(name, value)

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.main import app  # noqa: E402


def application_openapi_schema() -> dict[str, Any]:
    """Return FastAPI's schema without starting the application's lifespan."""
    return app.openapi()


def _serialized_schema() -> str:
    return json.dumps(application_openapi_schema(), indent=2, sort_keys=True) + "\n"


def export_openapi_spec(output: Path) -> None:
    """Write the deterministic OpenAPI input consumed by the web SDK generator."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_serialized_schema(), encoding="utf-8")


def openapi_input_is_current(output: Path) -> bool:
    """Return whether a checked-in OpenAPI input exactly matches the application."""
    return output.is_file() and output.read_text(encoding="utf-8") == _serialized_schema()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the checked-in input is missing or stale",
    )
    args = parser.parse_args()

    if args.check:
        return 0 if openapi_input_is_current(args.output) else 1

    export_openapi_spec(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
