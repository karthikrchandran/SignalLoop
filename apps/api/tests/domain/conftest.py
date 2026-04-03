"""Domain tests are pure unit tests — no database connection required.

This local conftest overrides the session-level autouse `db` fixture defined
in the parent conftest so that running the domain/ folder in isolation doesn't
require a live PostgreSQL instance.
"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def db():  # type: ignore[override]
    """No-op override: domain tests are pure unit tests."""
    yield None
