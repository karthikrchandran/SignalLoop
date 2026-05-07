"""Local conftest for unit tests — overrides the session-level autouse ``db`` fixture.

Unit tests in this folder are pure (no Postgres required), so we replace the
parent ``db`` fixture with a no-op to avoid spinning up a real database.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def db():  # type: ignore[override]
    """No-op override: unit tests don't require a live database."""
    yield None
