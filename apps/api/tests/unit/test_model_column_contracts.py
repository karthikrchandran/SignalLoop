from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlmodel import col

from app.domain.workspaces.models import Workspace
from app.domain_models import Campaign, Contact, WorkspaceRuntimeConfig


def test_explicit_timestamp_columns_preserve_timezone_defaults() -> None:
    for model in (Workspace, Campaign):
        for name in ("created_at", "updated_at"):
            column = model.__table__.c[name]
            assert isinstance(column.type, DateTime)
            assert column.type.timezone is True
            assert column.nullable is False
            assert column.default is not None
    value = Workspace(id="column-contract")
    assert value.created_at.tzinfo == timezone.utc
    assert value.updated_at.tzinfo == timezone.utc


def test_explicit_string_columns_preserve_lengths_indexes_and_primary_keys() -> None:
    workspace_column = Campaign.__table__.c.workspace_id
    assert isinstance(workspace_column.type, String)
    assert workspace_column.type.length == 64
    assert workspace_column.nullable is False
    assert workspace_column.index is True
    primary = WorkspaceRuntimeConfig.__table__.c.workspace_id
    assert primary.primary_key is True
    assert primary.type.length == 64
    assert primary.nullable is False
    assert Contact.__table__.c.last_seen_at.nullable is True


def test_col_returns_the_original_runtime_expression() -> None:
    assert col(Campaign.created_at) is Campaign.created_at
    expression = col(Campaign.created_at) >= datetime.now(timezone.utc)
    assert expression.left.name == "created_at"
