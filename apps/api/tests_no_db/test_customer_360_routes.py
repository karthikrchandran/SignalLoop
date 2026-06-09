from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from app.domain_models import Account, Contact


def _sqlite_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_customer_360_routes_are_registered() -> None:
    from app.api.main import api_router

    paths = {route.path for route in api_router.routes}

    assert "/customer-360/accounts" in paths
    assert "/customer-360/accounts/{account_id}" in paths


def test_customer_360_route_functions_return_sqlite_payload() -> None:
    from app.api.routes.customer_360 import (
        get_customer_360_account_profile,
        read_customer_360_accounts,
    )

    workspace_id = f"ws-c360-no-db-{uuid.uuid4().hex[:8]}"
    with _sqlite_session() as session:
        account = Account(
            workspace_id=workspace_id,
            name="Analytical",
            account_key=f"analytical-{uuid.uuid4().hex[:8]}",
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        contact = Contact(
            workspace_id=workspace_id,
            account_id=account.id,
            email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company=account.name,
        )
        session.add(contact)
        session.commit()

        listing = read_customer_360_accounts(
            session=session,
            workspace_id=workspace_id,
        )
        detail = get_customer_360_account_profile(
            account_id=account.id,
            session=session,
            workspace_id=workspace_id,
        )

    assert listing.count == 1
    assert listing.data[0].name == "Analytical"
    assert listing.data[0].contact_count == 1
    assert detail.account.name == "Analytical"
    assert detail.contacts[0].display_name == "Ada Lovelace"
    assert detail.channel_summaries["chatbot"].count == 0


def test_customer_360_route_function_raises_404_for_wrong_workspace() -> None:
    from app.api.routes.customer_360 import get_customer_360_account_profile

    with _sqlite_session() as session:
        account = Account(
            workspace_id="ws-owner",
            name="Compiler Co",
            account_key=f"compiler-co-{uuid.uuid4().hex[:8]}",
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        with pytest.raises(HTTPException) as exc_info:
            get_customer_360_account_profile(
                account_id=account.id,
                session=session,
                workspace_id="ws-other",
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Account not found"
