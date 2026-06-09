from __future__ import annotations

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.accounts.service import (
    account_to_public,
    find_or_create_account_for_company,
    generate_account_key,
)
from app.domain_models import Account


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


def test_find_or_create_account_ignores_blank_company() -> None:
    with _session() as session:
        account = find_or_create_account_for_company(
            session,
            workspace_id="ws-a",
            company_name=" ",
        )

    assert account is None


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
