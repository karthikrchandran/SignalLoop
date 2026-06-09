from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.accounts.service import (
    account_to_public,
    find_or_create_account_for_company,
    generate_account_key,
)
from app.domain_models import (
    Account,
    AccountContactAssignment,
    AccountContactAssignmentPublic,
)


def _session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_generate_account_key_normalizes_company_name() -> None:
    assert generate_account_key("  Analytical Health, Inc.  ") == "analytical-health-inc"
    assert generate_account_key("ACME___Clinic!!!") == "acme-clinic"


def test_find_or_create_account_reuses_account_by_workspace_and_key() -> None:
    with _session() as session:
        first = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health, Inc.",
        )
        second = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health Inc",
        )
        other_workspace = find_or_create_account_for_company(
            session,
            workspace_id="ws-b",
            company_name="Analytical Health Inc",
        )
        session.commit()

        accounts = session.exec(select(Account)).all()

    assert first.id == second.id
    assert other_workspace.id != first.id
    assert len(accounts) == 2
    assert first.name == "Analytical Health, Inc."
    assert first.account_key == "analytical-health-inc"


class _EmptyResult:
    def first(self) -> None:
        return None


def test_find_or_create_account_reselects_after_duplicate_key_race(
    monkeypatch: MonkeyPatch,
) -> None:
    with _session() as session:
        existing = Account(
            workspace_id="ws-a",
            name="Analytical Health Inc",
            account_key="analytical-health-inc",
        )
        session.add(existing)
        session.commit()
        session.refresh(existing)

        real_exec = session.exec
        select_calls = 0

        def exec_with_initial_miss(statement, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            nonlocal select_calls
            select_calls += 1
            if select_calls == 1:
                return _EmptyResult()
            return real_exec(statement, *args, **kwargs)

        monkeypatch.setattr(session, "exec", exec_with_initial_miss)

        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name="Analytical Health, Inc.",
        )

    assert account.id == existing.id
    assert select_calls == 2


def test_find_or_create_account_ignores_blank_company() -> None:
    with _session() as session:
        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name=" ",
        )
        accounts = session.exec(select(Account)).all()

    assert account is None
    assert accounts == []


def test_account_to_public_maps_fields() -> None:
    account = Account(
        workspace_id="ws-a",
        name="Analytical Health",
        account_key="analytical-health",
        website_url="https://analytical.example",
        industry="Healthcare",
        status="active",
        summary="Multi-location buyer.",
        tags_json=["pricing", "voice-ready"],
    )

    public = account_to_public(account)

    assert public.name == "Analytical Health"
    assert public.website_url == "https://analytical.example"
    assert public.tags == ["pricing", "voice-ready"]


def test_account_contact_assignment_schema_matches_plan() -> None:
    contact_id = uuid.uuid4()

    assignment = AccountContactAssignment(contact_ids=[contact_id])
    public = AccountContactAssignmentPublic(account_id=uuid.uuid4())

    assert assignment.contact_ids == [contact_id]
    assert public.assigned_count == 0
    assert public.unassigned_count == 0
    assert public.contact_ids == []
    with pytest.raises(ValidationError):
        AccountContactAssignment(contact_ids=[])
