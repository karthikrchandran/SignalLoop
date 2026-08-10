from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import Settings, settings
from app.integrations import ecrm_shared_records as ecrm_mod
from app.integrations.ecrm_shared_records import (
    EcrmSharedRecordNotFound,
    EcrmSharedRecordsClient,
    EcrmSharedRecordsError,
    EcrmSharedRecordsUnauthorized,
)


class _Recorder:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def __call__(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response


def test_settings_include_ecrm_shared_records_defaults() -> None:
    fields = Settings.model_fields

    assert fields["ECRM_SHARED_API_BASE_URL"].default == "http://localhost:5050"
    assert fields["ECRM_SHARED_API_TOKEN"].default == ""
    assert fields["USE_ECRM_SHARED_RECORDS"].default is True


def test_list_shared_records_sends_bearer_token_and_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(httpx.Response(200, json={"items": [{"id": "rec-1"}]}))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(
        base_url="https://crm.example/",
        token="secret-token",
    )
    result = client.list_shared_records(
        entity_type="contact",
        q="Ada",
        status="active",
        parent_id="acct-1",
        limit=25,
    )

    assert result == {"items": [{"id": "rec-1"}]}
    assert recorder.calls == [
        {
            "method": "GET",
            "url": "https://crm.example/api/shared-records",
            "headers": {"Authorization": "Bearer secret-token"},
            "params": {
                "entityType": "contact",
                "q": "Ada",
                "status": "active",
                "parentId": "acct-1",
                "limit": 25,
            },
            "timeout": 10.0,
        }
    ]


def test_list_shared_records_export_page_sends_bearer_token_and_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(
        httpx.Response(
            200,
            json={"items": [{"id": "rec-1"}], "nextCursor": "cursor-2"},
        )
    )
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(
        base_url="https://crm.example/",
        token="secret-token",
    )
    result = client.list_shared_records_export_page(
        entity_type="CONTACT",
        cursor="cursor-1",
        limit=500,
    )

    assert result == {"items": [{"id": "rec-1"}], "nextCursor": "cursor-2"}
    assert recorder.calls == [
        {
            "method": "GET",
            "url": "https://crm.example/api/shared-records/export",
            "headers": {"Authorization": "Bearer secret-token"},
            "params": {
                "entityType": "CONTACT",
                "cursor": "cursor-1",
                "limit": 500,
            },
            "timeout": 10.0,
        }
    ]


def test_empty_token_fails_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder(httpx.Response(200, json={}))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="")

    with pytest.raises(EcrmSharedRecordsError, match="ECRM_SHARED_API_TOKEN"):
        client.get_shared_record("rec-1")

    assert recorder.calls == []


def test_unauthorized_status_maps_to_unauthorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(httpx.Response(401, text="unauthorized"))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="bad-token")

    with pytest.raises(EcrmSharedRecordsUnauthorized):
        client.list_shared_records()


def test_get_shared_record_404_maps_to_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(httpx.Response(404, text="missing"))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="token")

    with pytest.raises(EcrmSharedRecordNotFound, match="rec-404"):
        client.get_shared_record("rec-404")


def test_upsert_shared_record_success_returns_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(
        httpx.Response(201, json={"id": "rec-1", "entity_type": "account"})
    )
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="token")
    result = client.upsert_shared_record(
        {"id": "rec-1", "entity_type": "account", "name": "Acme"}
    )

    assert result == {"id": "rec-1", "entity_type": "account"}
    assert recorder.calls[0]["method"] == "POST"
    assert recorder.calls[0]["url"] == "https://crm.example/api/shared-records"
    assert recorder.calls[0]["json"] == {
        "id": "rec-1",
        "entity_type": "account",
        "name": "Acme",
    }


def test_success_response_invalid_json_maps_to_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(httpx.Response(200, content=b"not-json"))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="token")

    with pytest.raises(EcrmSharedRecordsError, match="invalid JSON"):
        client.get_shared_record("rec-1")


def test_generic_upstream_error_body_is_sanitized_and_truncated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_body = "line 1\n" + ("x" * 500)
    recorder = _Recorder(httpx.Response(502, text=long_body))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)

    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="token")

    with pytest.raises(EcrmSharedRecordsError) as exc_info:
        client.list_shared_records()

    message = str(exc_info.value)
    body = message.split("body=", maxsplit=1)[1]
    assert "\n" not in message
    assert len(body) <= 300
    assert "x" * 301 not in message


def test_module_functions_use_configured_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _Recorder(httpx.Response(200, json={"id": "rec-1"}))
    monkeypatch.setattr(ecrm_mod.httpx, "request", recorder)
    monkeypatch.setattr(
        settings, "ECRM_SHARED_API_BASE_URL", "https://settings.example"
    )
    monkeypatch.setattr(settings, "ECRM_SHARED_API_TOKEN", "settings-token")

    assert ecrm_mod.get_shared_record("rec-1") == {"id": "rec-1"}

    assert (
        recorder.calls[0]["url"] == "https://settings.example/api/shared-records/rec-1"
    )
    assert recorder.calls[0]["headers"] == {
        "Authorization": "Bearer settings-token",
    }


def test_create_read_update_smoke_uses_same_shared_record_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        httpx.Response(
            201, json={"record": {"id": "rec-1", "displayName": "Ada"}, "created": True}
        ),
        httpx.Response(200, json={"record": {"id": "rec-1", "displayName": "Ada"}}),
        httpx.Response(
            200,
            json={
                "record": {"id": "rec-1", "displayName": "Ada Updated"},
                "created": False,
            },
        ),
    ]
    calls: list[dict[str, Any]] = []

    def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        calls.append({"method": method, "url": url, **kwargs})
        return responses.pop(0)

    monkeypatch.setattr(ecrm_mod.httpx, "request", request)
    client = EcrmSharedRecordsClient(base_url="https://crm.example", token="token")

    created = client.upsert_shared_record(
        {
            "entityType": "CONTACT",
            "displayName": "Ada",
            "status": "active",
            "sourceApp": "emailvoice",
            "emailVoiceLegacyId": "contact-1",
            "externalKey": "emailvoice:contact:ws-a:ada@example.com",
            "email": "ada@example.com",
            "data": {"workspaceId": "ws-a"},
        }
    )
    fetched = client.get_shared_record("rec-1")
    updated = client.upsert_shared_record(
        {
            "entityType": "CONTACT",
            "displayName": "Ada Updated",
            "status": "active",
            "sourceApp": "emailvoice",
            "emailVoiceLegacyId": "contact-1",
            "externalKey": "emailvoice:contact:ws-a:ada@example.com",
            "email": "ada@example.com",
            "data": {"workspaceId": "ws-a"},
        }
    )

    assert created["created"] is True
    assert fetched["record"]["id"] == "rec-1"
    assert updated["record"]["displayName"] == "Ada Updated"
    assert [(call["method"], call["url"]) for call in calls] == [
        ("POST", "https://crm.example/api/shared-records"),
        ("GET", "https://crm.example/api/shared-records/rec-1"),
        ("POST", "https://crm.example/api/shared-records"),
    ]
