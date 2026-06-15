from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_current_user, get_db
from app.api.routes import customer_360
from app.domain_models import Account, Contact
from app.models import User


def _sqlite_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _user(*, is_superuser: bool, role: str = "operator") -> User:
    return User(
        email=f"user-{uuid.uuid4().hex[:8]}@example.com",
        hashed_password="not-used",
        is_superuser=is_superuser,
        role=role,
    )


def _customer_360_app(session: Session, *, user: User | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(customer_360.router)

    def override_get_db() -> Session:
        return session

    app.dependency_overrides[get_db] = override_get_db
    if user is not None:

        def override_get_current_user() -> User:
            return user

        app.dependency_overrides[get_current_user] = override_get_current_user
    return app


def _seed_account_with_contact(
    session: Session,
    *,
    workspace_id: str,
) -> Account:
    account = Account(
        workspace_id=workspace_id,
        name="Analytical",
        account_key=f"analytical-{uuid.uuid4().hex[:8]}",
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    session.add(
        Contact(
            workspace_id=workspace_id,
            account_id=account.id,
            email=f"ada-{uuid.uuid4().hex[:8]}@example.com",
            first_name="Ada",
            last_name="Lovelace",
            company=account.name,
        ),
    )
    session.commit()
    return account


def test_customer_360_routes_are_registered() -> None:
    from app.api.main import api_router

    paths = {route.path for route in api_router.routes}

    assert "/customer-360/accounts" in paths
    assert "/customer-360/accounts/{account_id}" in paths


def test_customer_360_route_functions_document_plan_intent() -> None:
    assert "account-first" in (customer_360.read_customer_360_accounts.__doc__ or "")
    assert "Account Command Center" in (
        customer_360.get_customer_360_account_profile.__doc__ or ""
    )


def test_customer_360_front_door_rejects_unauthenticated_request() -> None:
    with _sqlite_session() as session:
        app = _customer_360_app(session)
        with TestClient(app) as client:
            response = client.get(
                "/customer-360/accounts",
                headers={"X-Workspace-Id": "ws-auth"},
            )

    assert response.status_code == 401


def test_customer_360_front_door_rejects_non_admin_user() -> None:
    with _sqlite_session() as session:
        app = _customer_360_app(
            session,
            user=_user(is_superuser=False, role="operator"),
        )
        with TestClient(app) as client:
            response = client.get(
                "/customer-360/accounts",
                headers={"X-Workspace-Id": "ws-auth"},
            )

    assert response.status_code == 403
    assert response.json()["detail"]["error"]["code"] == "AUTH_ERROR"


def test_customer_360_front_door_rejects_missing_workspace_header() -> None:
    with _sqlite_session() as session:
        app = _customer_360_app(
            session,
            user=_user(is_superuser=True, role="super_admin"),
        )
        with TestClient(app) as client:
            response = client.get("/customer-360/accounts")

    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "WORKSPACE_REQUIRED"


@pytest.mark.parametrize("limit", [0, 101])
def test_customer_360_front_door_rejects_limit_outside_bounds(limit: int) -> None:
    with _sqlite_session() as session:
        app = _customer_360_app(
            session,
            user=_user(is_superuser=True, role="super_admin"),
        )
        with TestClient(app) as client:
            response = client.get(
                "/customer-360/accounts",
                params={"limit": limit},
                headers={"X-Workspace-Id": "ws-validation"},
            )

    assert response.status_code == 422


def test_customer_360_front_door_rejects_overlong_search() -> None:
    with _sqlite_session() as session:
        app = _customer_360_app(
            session,
            user=_user(is_superuser=True, role="super_admin"),
        )
        with TestClient(app) as client:
            response = client.get(
                "/customer-360/accounts",
                params={"search": "x" * 256},
                headers={"X-Workspace-Id": "ws-validation"},
            )

    assert response.status_code == 422


def test_customer_360_front_door_returns_sqlite_payload() -> None:
    workspace_id = f"ws-c360-http-{uuid.uuid4().hex[:8]}"
    with _sqlite_session() as session:
        account = _seed_account_with_contact(session, workspace_id=workspace_id)
        app = _customer_360_app(
            session,
            user=_user(is_superuser=True, role="super_admin"),
        )
        with TestClient(app) as client:
            list_response = client.get(
                "/customer-360/accounts",
                headers={"X-Workspace-Id": workspace_id},
            )
            detail_response = client.get(
                f"/customer-360/accounts/{account.id}",
                headers={"X-Workspace-Id": workspace_id},
            )

    assert list_response.status_code == 200
    listing = list_response.json()
    assert listing["count"] == 1
    assert listing["data"][0]["name"] == "Analytical"
    assert listing["data"][0]["contact_count"] == 1

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["account"]["name"] == "Analytical"
    assert detail["contacts"][0]["display_name"] == "Ada Lovelace"
    assert detail["channel_summaries"]["chatbot"]["count"] == 0


def test_customer_360_route_functions_return_sqlite_payload() -> None:
    workspace_id = f"ws-c360-no-db-{uuid.uuid4().hex[:8]}"
    with _sqlite_session() as session:
        account = _seed_account_with_contact(session, workspace_id=workspace_id)
        listing = customer_360.read_customer_360_accounts(
            session=session,
            workspace_id=workspace_id,
        )
        detail = customer_360.get_customer_360_account_profile(
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
            customer_360.get_customer_360_account_profile(
                account_id=account.id,
                session=session,
                workspace_id="ws-other",
            )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Account not found"
