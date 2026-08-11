from fastapi.testclient import TestClient

from app.main import app


def test_known_local_domain_returns_safe_branding() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/public/entry", headers={"host": "ara.localhost"})
    assert response.status_code == 200
    assert response.json()["tenant_key"] == "ara-global"
    assert response.json()["oidc_start_url"] == "/api/v1/auth/oidc/start"
    assert response.json()["products"] == ["CommitArc", "RevenueOS", "SignalLoop"]
    assert "support_email" not in response.json()


def test_unknown_domain_discloses_nothing() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/public/entry", headers={"host": "unknown.test"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Workspace is not available"}


def test_query_cannot_select_tenant() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/public/entry?tenant=ara-global", headers={"host": "unknown.test"}
        )
    assert response.status_code == 404
