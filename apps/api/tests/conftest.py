from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.core.rate_limit import limiter
from app.main import app
from app.models import User, WorkspaceMembership
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


def _clear_users(session: Session) -> None:
    session.rollback()
    session.execute(delete(WorkspaceMembership))
    session.execute(delete(User))
    session.commit()


def _ensure_pgvector_extension(session: Session) -> bool:
    if engine.dialect.name != "postgresql":
        return True
    try:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        return False
    return True


def _table_uses_pgvector(table) -> bool:  # noqa: ANN001
    return any("vector" in str(column.type).lower() for column in table.columns)


def _metadata_tables_for_available_extensions(pgvector_available: bool):
    if pgvector_available:
        return None
    return [
        table
        for table in SQLModel.metadata.sorted_tables
        if not _table_uses_pgvector(table)
    ]


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    """Disable slowapi rate limiting for all tests so token fixtures don't hit 429."""
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        pgvector_available = _ensure_pgvector_extension(session)
        SQLModel.metadata.create_all(
            engine,
            tables=_metadata_tables_for_available_extensions(pgvector_available),
        )
        _clear_users(session)
        init_db(session)
        yield session
        _clear_users(session)
        init_db(session)


@pytest.fixture(autouse=True)
def reset_db_session_state(db: Session) -> Generator[None, None, None]:
    """Keep the shared session usable between tests even after rollback-triggering failures."""
    if db is None:
        yield
        return
    db.rollback()
    db.expire_all()
    yield
    db.rollback()
    db.expire_all()


@pytest.fixture(scope="module")
def client(db: Session) -> Generator[TestClient, None, None]:  # noqa: ARG001
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
