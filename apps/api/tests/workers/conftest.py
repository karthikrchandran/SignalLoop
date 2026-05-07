"""Local conftest for worker tests.

Overrides the session-level autouse ``db`` fixture so worker unit tests don't
require a live PostgreSQL instance.
"""
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel


@pytest.fixture(scope="session", autouse=True)
def db():  # type: ignore[override]
    """No-op override: worker unit tests don't require a live database."""
    yield None


@pytest.fixture()
def memory_session() -> Generator[Session, None, None]:
    """Provide a fresh in-memory SQLite ``Session`` per test."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
