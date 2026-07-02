"""Client for the future eCRM shared-records API."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

_SHARED_RECORDS_PATH = "/api/shared-records"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_ERROR_BODY_CHARS = 300


class EcrmSharedRecordsError(RuntimeError):
    """Base error for eCRM shared-records API failures."""


class EcrmSharedRecordsUnauthorized(EcrmSharedRecordsError):
    """Raised when eCRM shared-records credentials are rejected."""


class EcrmSharedRecordNotFound(EcrmSharedRecordsError):
    """Raised when a requested eCRM shared record does not exist."""


class EcrmSharedRecordsClient:
    """Small synchronous client for shared CRM records."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ECRM_SHARED_API_BASE_URL).rstrip("/")
        self._token = token if token is not None else settings.ECRM_SHARED_API_TOKEN

    def list_shared_records(
        self,
        entity_type: str | None = None,
        q: str | None = None,
        status: str | None = None,
        parent_id: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List shared records, optionally filtered for adapter consumers."""
        params = {
            key: value
            for key, value in {
                "entityType": entity_type,
                "q": q,
                "status": status,
                "parentId": parent_id,
                "limit": limit,
            }.items()
            if value is not None
        }
        return self._request("GET", _SHARED_RECORDS_PATH, params=params)

    def get_shared_record(self, record_id: str) -> dict[str, Any]:
        """Fetch one shared record by ID."""
        return self._request(
            "GET",
            f"{_SHARED_RECORDS_PATH}/{record_id}",
            not_found_record_id=record_id,
        )

    def upsert_shared_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create or update one shared record."""
        return self._request("POST", _SHARED_RECORDS_PATH, json=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        not_found_record_id: str | None = None,
    ) -> dict[str, Any]:
        token = str(self._token or "").strip()
        if not token:
            raise EcrmSharedRecordsError("ECRM_SHARED_API_TOKEN is required")

        request_kwargs: dict[str, Any] = {
            "headers": {"Authorization": f"Bearer {token}"},
            "timeout": _REQUEST_TIMEOUT_SECONDS,
        }
        if params is not None:
            request_kwargs["params"] = params
        if json is not None:
            request_kwargs["json"] = json

        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                **request_kwargs,
            )
        except httpx.HTTPError as exc:
            raise EcrmSharedRecordsError(
                f"eCRM shared-records request failed: {type(exc).__name__}"
            ) from exc

        return _handle_response(response, not_found_record_id=not_found_record_id)


def list_shared_records(
    entity_type: str | None = None,
    q: str | None = None,
    status: str | None = None,
    parent_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """List shared records using configured eCRM shared-records settings."""
    return EcrmSharedRecordsClient().list_shared_records(
        entity_type=entity_type,
        q=q,
        status=status,
        parent_id=parent_id,
        limit=limit,
    )


def get_shared_record(record_id: str) -> dict[str, Any]:
    """Fetch one shared record using configured eCRM shared-records settings."""
    return EcrmSharedRecordsClient().get_shared_record(record_id)


def upsert_shared_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert one shared record using configured eCRM shared-records settings."""
    return EcrmSharedRecordsClient().upsert_shared_record(payload)


def _handle_response(
    response: httpx.Response,
    *,
    not_found_record_id: str | None = None,
) -> dict[str, Any]:
    if response.status_code in (200, 201):
        try:
            payload = response.json()
        except ValueError as exc:
            raise EcrmSharedRecordsError(
                "eCRM shared-records API returned invalid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise EcrmSharedRecordsError(
                "eCRM shared-records API returned a non-object JSON response"
            )
        return payload

    if response.status_code in (401, 403):
        raise EcrmSharedRecordsUnauthorized(
            f"eCRM shared-records API rejected credentials: {response.status_code}"
        )

    if response.status_code == 404 and not_found_record_id is not None:
        raise EcrmSharedRecordNotFound(
            f"eCRM shared record not found: {not_found_record_id}"
        )

    raise EcrmSharedRecordsError(
        f"eCRM shared-records API request failed: "
        f"status={response.status_code} body={_safe_error_body(response.text)}"
    )


def _safe_error_body(body: str) -> str:
    normalized = " ".join(body.split())
    return normalized[:_MAX_ERROR_BODY_CHARS]
