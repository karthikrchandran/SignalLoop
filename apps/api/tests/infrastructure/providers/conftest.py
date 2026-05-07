"""Pure-unit conftest for provider adapter tests.

Overrides the session-scoped autouse ``db`` fixture from
``tests/conftest.py`` so these tests do not require a database — they
only exercise provider adapter logic with mocked HTTP/network layers.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[None, None, None]:
    """No-op override of the session-scoped ``db`` fixture."""
    yield None
