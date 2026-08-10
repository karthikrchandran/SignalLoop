from typing import Any, cast

import pytest
from sqlalchemy import UniqueConstraint, create_engine
from sqlmodel import Session

from app.api.routes import webhooks
from app.domain.sequences import suppression


def _session() -> Session:
    engine = create_engine("sqlite://")
    cast(Any, suppression.EmailSuppression).__table__.create(engine)
    return Session(engine)


def test_email_suppression_schema_is_workspace_scoped() -> None:
    table = cast(Any, suppression.EmailSuppression).__table__
    workspace_column = table.columns.get("workspace_id")

    assert workspace_column is not None, "EmailSuppression must store workspace ownership"
    assert workspace_column.nullable is False
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("workspace_id", "email", "reason") in unique_column_sets
    assert ("email", "reason") not in unique_column_sets


def test_identical_suppressions_can_exist_in_two_workspaces() -> None:
    table = cast(Any, suppression.EmailSuppression).__table__
    if "workspace_id" not in table.columns:
        pytest.fail("EmailSuppression must store workspace ownership")

    with _session() as session:
        session.add(
            suppression.EmailSuppression(
                workspace_id="workspace-a",
                email="lead@example.com",
                reason="unsubscribe",
            )
        )
        session.add(
            suppression.EmailSuppression(
                workspace_id="workspace-b",
                email="lead@example.com",
                reason="unsubscribe",
            )
        )

        session.commit()


def test_suppression_in_workspace_a_does_not_suppress_workspace_b() -> None:
    is_email_suppressed = getattr(suppression, "is_email_suppressed", None)
    if is_email_suppressed is None:
        pytest.fail("workspace-scoped suppression lookup is required")

    with _session() as session:
        session.add(
            suppression.EmailSuppression(
                workspace_id="workspace-a",
                email="lead@example.com",
                reason="unsubscribe",
            )
        )
        session.commit()

        assert is_email_suppressed(session, "workspace-a", "lead@example.com") is True
        assert is_email_suppressed(session, "workspace-b", "lead@example.com") is False


def test_webhook_suppression_records_the_resolved_workspace() -> None:
    with _session() as session:
        webhooks._add_suppression(
            session,
            "lead@example.com",
            "unsubscribe",
            "workspace-a",
        )
        row = next(
            item
            for item in session.new
            if isinstance(item, suppression.EmailSuppression)
        )

        assert row.workspace_id == "workspace-a"
