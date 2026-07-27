from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module", autouse=True)
def db():  # type: ignore[override]
    """No-op override of the parent autouse ``db`` fixture; this is a file-content test."""
    yield None


def test_demo_up_seeds_initial_login_user_before_provider_selections() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "tooling" / "demo-up.ps1"
    contents = script.read_text(encoding="utf-8")

    initial_data_index = contents.index("uv run python -m app.initial_data")
    provider_seed_index = contents.index("tooling/seed_demo_providers.py")

    assert initial_data_index < provider_seed_index


def test_demo_up_uses_local_shared_records_for_unconfigured_browser_demos() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    contents = (repo_root / "tooling" / "demo-up.ps1").read_text(encoding="utf-8")

    assert "`$env:USE_LOCAL_SHARED_RECORDS='true';" in contents


def test_demo_up_forces_utf8_for_fastapi_startup_output_on_windows() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    contents = (repo_root / "tooling" / "demo-up.ps1").read_text(encoding="utf-8")

    assert "`$env:PYTHONIOENCODING='utf-8';" in contents
