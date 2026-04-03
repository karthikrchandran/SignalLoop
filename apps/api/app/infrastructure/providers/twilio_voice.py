"""Twilio Voice adapter for outbound calling and media streaming."""
from __future__ import annotations

import hashlib
import hmac
import logging
from base64 import b64encode
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioVoiceAdapter:
    """Twilio Voice REST API adapter using httpx."""

    def __init__(self) -> None:
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_PHONE_NUMBER

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
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, auth=auth)
            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    "call_sid": result.get("sid", ""),
                    "status": result.get("status", ""),
                }
            logger.error("Twilio call failed: %d %s", resp.status_code, resp.text)
            return {"call_sid": "", "status": "failed", "error": resp.text}

    @staticmethod
    def verify_request_signature(
        url: str, params: dict[str, str], signature: str
    ) -> bool:
        """Verify Twilio request signature (X-Twilio-Signature)."""
        auth_token = settings.TWILIO_AUTH_TOKEN
        if not auth_token:
            return False
        # Build the data string per Twilio's spec
        data_string = url + "".join(
            f"{k}{v}" for k, v in sorted(params.items())
        )
        expected = b64encode(
            hmac.new(
                auth_token.encode("utf-8"),
                data_string.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        return hmac.compare_digest(expected, signature)
