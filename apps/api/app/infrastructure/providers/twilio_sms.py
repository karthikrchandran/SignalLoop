"""Twilio SMS adapter."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.infrastructure.providers.base import SmsAdapter

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class TwilioSmsAdapter(SmsAdapter):
    """Send SMS messages through Twilio's Messages API."""

    def __init__(
        self,
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
    ) -> None:
        self._account_sid = account_sid or settings.TWILIO_ACCOUNT_SID
        self._auth_token = auth_token or settings.TWILIO_AUTH_TOKEN
        self._from_number = from_number or settings.TWILIO_PHONE_NUMBER

    async def send_sms(self, *, to: str, message: str, **kwargs: Any) -> dict[str, Any]:
        """Send a single SMS message."""
        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        auth = (self._account_sid, self._auth_token)
        data = {
            "To": to,
            "From": self._from_number,
            "Body": message,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, auth=auth)
            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    "status_code": resp.status_code,
                    "message_sid": result.get("sid", ""),
                    "status": result.get("status", ""),
                }
            error_code = _twilio_error_code(resp)
            logger.error("Twilio SMS failed: status=%d code=%s", resp.status_code, error_code)
            return {
                "status_code": resp.status_code,
                "message_sid": "",
                "status": "failed",
                "error": "twilio_sms_failed",
                "error_code": error_code,
            }


def _twilio_error_code(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
    except ValueError:
        return "http_error"
    code = payload.get("code")
    return str(code) if code else "twilio_error"
