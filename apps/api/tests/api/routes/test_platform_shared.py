from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import deps, request_context
from app.api.routes import platform_shared
from app.core.config import settings

WORKSPACE_ID = "ws-platform-shared"


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[None, None, None]:
    yield None


@pytest.fixture(autouse=True)
def reset_db_session_state() -> Generator[None, None, None]:
    yield


def _build_app(*, session: object | None = None, allow_admin: bool = False) -> FastAPI:
    app = FastAPI()

    def fake_db() -> Generator[object, None, None]:
        yield session if session is not None else object()

    app.include_router(platform_shared.router, prefix=settings.API_V1_STR)
    app.dependency_overrides[deps.get_db] = fake_db
    app.dependency_overrides[request_context.require_workspace_id] = lambda: WORKSPACE_ID
    if allow_admin:
        app.dependency_overrides[deps.require_admin] = lambda: object()
    return app


def test_platform_shared_reconciliation_requires_authentication(
) -> None:
    app = _build_app()
    client = TestClient(app)

    try:
        response = client.get(f"{settings.API_V1_STR}/platform-shared/reconciliation")
    finally:
        client.close()

    assert response.status_code == 401


def test_platform_shared_reconciliation_returns_admin_report(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    session = object()
    expected = {
        "status": "mismatch",
        "diffs": [{"entity": "CONTACT", "expected": 5, "actual": 4}],
        "ecrm_counts": {"CUSTOMER": 2, "CONTACT": 5},
        "local_counts": {"CUSTOMER": 2, "CONTACT": 4},
    }

    def fake_reconcile_with_ecrm(*, session, workspace_id: str) -> dict[str, object]:
        captured["session"] = session
        captured["workspace_id"] = workspace_id
        return expected

    monkeypatch.setattr(
        "app.api.routes.platform_shared.shared_record_service.reconcile_with_ecrm",
        fake_reconcile_with_ecrm,
    )

    app = _build_app(session=session, allow_admin=True)
    client = TestClient(app)

    try:
        response = client.get(
            f"{settings.API_V1_STR}/platform-shared/reconciliation",
            headers={"X-Workspace-Id": WORKSPACE_ID},
        )
    finally:
        client.close()

    assert response.status_code == 200
    assert response.json() == expected
    assert captured["session"] is session
    assert captured["workspace_id"] == WORKSPACE_ID
