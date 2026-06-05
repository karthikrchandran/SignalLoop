"""Twilio Voice adapter for outbound calling and media streaming."""
from __future__ import annotations

import hashlib
import hmac
import logging
from base64 import b64encode
from typing import Any

import httpx

from app.core.config import settings
from app.infrastructure.providers.base import VoiceAdapter

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioVoiceAdapter(VoiceAdapter):
    """Twilio Voice REST API adapter using httpx.

    Credentials can be injected at construction time (multi-tenant path via
    :func:`~app.domain.providers.credential_resolver.resolve_provider_credentials`)
    or omitted to fall back to ``settings.*`` (single-tenant / demo mode).
    """

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ) -> None:
        self._account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self._auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self._from_number = from_number or settings.TWILIO_PHONE_NUMBER

    async def initiate_call(
        self,
        *,
        to: str,
        twiml_url: str,
        status_callback_url: str,
    ) -> dict[str, Any]:
        """Place an outbound call via Twilio REST API."""
        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Calls.json"
        auth = (self._account_sid, self._auth_token)

        data = {
            "To": to,
            "From": self._from_number,
            "Url": twiml_url,
            "StatusCallback": status_callback_url,
            "StatusCallbackEvent": "initiated ringing answered completed",
            "Record": "true",
            "RecordingStatusCallback": status_callback_url.replace("/status", "/recording"),
            "MachineDetection": "Enable",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, auth=auth)
            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    "call_sid": result.get("sid", ""),
                    "status": result.get("status", ""),
                }
            error_code = _twilio_error_code(resp)
            logger.error("Twilio call failed: status=%d code=%s", resp.status_code, error_code)
            return {
                "call_sid": "",
                "status": "failed",
                "error": "twilio_call_failed",
                "error_code": error_code,
            }

    @staticmethod
    def verify_request_signature(
        url: str,
        params: dict[str, str],
        signature: str,
        *,
        auth_token: str | None = None,
    ) -> bool:
        """Verify Twilio request signature (X-Twilio-Signature)."""
        token = auth_token if auth_token is not None else settings.TWILIO_AUTH_TOKEN
        if not token or not signature:
            return False
        # Build the data string per Twilio's spec
        data_string = url + "".join(
            f"{k}{v}" for k, v in sorted(params.items())
        )
        expected = b64encode(
            hmac.new(
                token.encode("utf-8"),
                data_string.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)


def _twilio_error_code(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        return "http_error"
    code = payload.get("code")
    return str(code) if code else "twilio_error"
