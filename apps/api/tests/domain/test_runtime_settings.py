from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.domain.runtime_settings import resolve_team_notification_email
from app.domain_models import WorkspaceRuntimeConfig


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_team_notification_email_is_strictly_workspace_scoped(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TEAM_NOTIFICATION_EMAIL", "global@example.com")
    session.add(
        WorkspaceRuntimeConfig(
            workspace_id="workspace-a",
            team_notification_email="a@example.com",
        )
    )
    session.add(
        WorkspaceRuntimeConfig(
            workspace_id="workspace-b",
            team_notification_email="b@example.com",
        )
    )
    session.commit()

    assert resolve_team_notification_email(session, "workspace-a") == "a@example.com"
    assert resolve_team_notification_email(session, "workspace-b") == "b@example.com"
    assert resolve_team_notification_email(session, "workspace-missing") == ""


def test_team_notification_email_global_fallback_is_singleton_only(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TEAM_NOTIFICATION_EMAIL", "global@example.com")
    monkeypatch.setattr(settings, "DEFAULT_WORKSPACE_ID", "singleton")

    assert resolve_team_notification_email(session, "singleton") == "global@example.com"
    assert resolve_team_notification_email(session, "tenant-a") == ""
