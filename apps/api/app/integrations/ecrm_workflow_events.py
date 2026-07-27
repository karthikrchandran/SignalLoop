"""Client for emitting workflow events into eCRM."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings

_WORKFLOW_EVENTS_PATH = "/api/workflow-events"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_ERROR_BODY_CHARS = 300


class EcrmWorkflowEventsError(RuntimeError):
    """Raised when eCRM workflow-event emission fails."""


class EcrmWorkflowEventsClient:
    """Small synchronous client for posting workflow events to eCRM."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ECRM_SHARED_API_BASE_URL).rstrip("/")
        self._token = token if token is not None else settings.ECRM_SHARED_API_TOKEN

    def emit_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Emit a workflow event to the dedicated eCRM workflow endpoint."""
        return self._request("POST", _WORKFLOW_EVENTS_PATH, json=payload)

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        token = str(self._token or "").strip()
        if not token:
            raise EcrmWorkflowEventsError("ECRM_SHARED_API_TOKEN is required")

        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                headers={"Authorization": f"Bearer {token}"},
                json=json,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            raise EcrmWorkflowEventsError(f"eCRM workflow-event request failed: {type(exc).__name__}") from exc

        if response.status_code in (200, 201):
            try:
                payload = response.json()
            except ValueError as exc:
                raise EcrmWorkflowEventsError("eCRM workflow-event API returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise EcrmWorkflowEventsError("eCRM workflow-event API returned a non-object JSON response")
            return payload

        if response.status_code in (401, 403):
            raise EcrmWorkflowEventsError(f"eCRM workflow-event API rejected credentials: {response.status_code}")

        raise EcrmWorkflowEventsError(
            f"eCRM workflow-event request failed: status={response.status_code} body={_safe_error_body(response.text)}"
        )


def emit_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Emit a workflow event using configured eCRM settings."""
    return EcrmWorkflowEventsClient().emit_event(payload)


def _safe_error_body(body: str) -> str:
    normalized = " ".join(body.split())
    return normalized[:_MAX_ERROR_BODY_CHARS]
