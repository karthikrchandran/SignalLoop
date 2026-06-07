"""Vapi voice adapter for managed outbound AI calls."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.infrastructure.providers.base import VoiceAdapter

logger = logging.getLogger(__name__)

VAPI_API_BASE_URL = "https://api.vapi.ai"
VAPI_CALL_ENDPOINT = "/call"
VAPI_TIMEOUT = httpx.Timeout(30.0)


class VapiVoiceAdapter(VoiceAdapter):
    """Vapi outbound-call adapter.

    The constructor intentionally does not fail when credentials are missing.
    The provider registry may receive an explicit Vapi selection with partial
    credentials, and in that case we want the call worker to return a Vapi
    failure payload instead of falling back to Twilio.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        phone_number_id: str | None = None,
        assistant_id: str | None = None,
        base_url: str | None = None,
        call_endpoint: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.VAPI_API_KEY
        self._phone_number_id = phone_number_id or settings.VAPI_PHONE_NUMBER_ID
        self._assistant_id = assistant_id or settings.VAPI_ASSISTANT_ID
        self._base_url = (base_url or settings.VAPI_API_BASE_URL or VAPI_API_BASE_URL).rstrip("/")
        self._call_endpoint = call_endpoint or settings.VAPI_CALL_ENDPOINT or VAPI_CALL_ENDPOINT

    async def initiate_call(
        self,
        *,
        to: str,
        twiml_url: str | None = None,
        status_callback_url: str | None = None,
        metadata: dict[str, Any] | None = None,
        assistant_overrides: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Place an outbound AI voice call via Vapi."""
        missing = self._missing_config()
        if missing:
            return {
                "call_sid": "",
                "status": "failed",
                "provider": "vapi",
                "error": "vapi_not_configured",
                "error_code": "missing_" + "_".join(missing),
            }

        payload: dict[str, Any] = {
            "phoneNumberId": self._phone_number_id,
            "assistantId": self._assistant_id,
            "customer": {"number": to},
        }
        if metadata:
            payload["metadata"] = metadata
        if assistant_overrides:
            payload["assistantOverrides"] = assistant_overrides

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=VAPI_TIMEOUT) as client:
                resp = await client.post(
                    self._call_url(),
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as exc:
            logger.exception("Vapi call request failed: error_type=%s", type(exc).__name__)
            return {
                "call_sid": "",
                "status": "failed",
                "provider": "vapi",
                "error": "vapi_request_failed",
                "error_code": type(exc).__name__,
            }

        if resp.status_code in (200, 201, 202):
            result = _safe_json(resp)
            call_id = _first_non_empty(result, "id", "callId", "sid")
            return {
                "call_sid": call_id,
                "provider_call_id": call_id,
                "status": str(result.get("status") or "initiated"),
                "provider": "vapi",
            }

        error_code = _vapi_error_code(resp)
        logger.error("Vapi call failed: status=%d code=%s", resp.status_code, error_code)
        return {
            "call_sid": "",
            "status": "failed",
            "provider": "vapi",
            "error": "vapi_call_failed",
            "error_code": error_code,
        }

    async def normalize_webhook_event(
        self, raw_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalize Vapi webhook payloads into the repo's provider event shape."""
        message = raw_payload.get("message")
        if not isinstance(message, dict):
            message = {}
        call = raw_payload.get("call") or message.get("call")
        if not isinstance(call, dict):
            call = {}

        provider_call_id = (
            _first_non_empty(call, "id", "callId", "sid")
            or _first_non_empty(message, "callId", "call_id")
            or _first_non_empty(raw_payload, "callId", "call_id", "id")
        )
        event_type = (
            str(message.get("type") or raw_payload.get("type") or raw_payload.get("event") or "call_event")
        )

        return {
            "event_type": event_type,
            "provider_event_id": (
                _first_non_empty(message, "id")
                or _first_non_empty(raw_payload, "id", "eventId")
                or provider_call_id
            ),
            "provider_call_id": provider_call_id,
            "status": raw_payload.get("status") or call.get("status"),
            "recording_url": raw_payload.get("recordingUrl") or call.get("recordingUrl"),
            "transcript": raw_payload.get("transcript") or call.get("transcript"),
            "raw_payload": raw_payload,
        }

    def _missing_config(self) -> list[str]:
        required = {
            "api_key": self._api_key,
            "phone_number_id": self._phone_number_id,
            "assistant_id": self._assistant_id,
        }
        return [
            key
            for key, value in required.items()
            if not str(value or "").strip()
        ]

    def _call_url(self) -> str:
        endpoint = self._call_endpoint
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint
        return f"{self._base_url}{endpoint}"


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        payload = resp.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_non_empty(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _vapi_error_code(resp: httpx.Response) -> str:
    payload = _safe_json(resp)
    error = payload.get("error")
    if isinstance(error, dict):
        code = error.get("code") or error.get("type")
        if code:
            return str(code)
    if isinstance(error, str) and error:
        return error[:80]
    code = payload.get("code") or payload.get("message")
    return str(code)[:80] if code else "vapi_error"
