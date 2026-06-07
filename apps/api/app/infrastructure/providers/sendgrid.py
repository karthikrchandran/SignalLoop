"""External provider adapter: ``sendgrid``."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.core.config import settings
from app.infrastructure.providers.base import NotificationProviderAdapter

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2  # seconds


class SendGridAdapter(NotificationProviderAdapter):
    """SendGrid email provider adapter using v3 API via httpx.

    Credentials can be injected at construction time or omitted to fall back
    to ``settings.*`` for single-tenant / demo mode.
    """

    def __init__(
        self,
        api_key: str | None = None,
        from_email: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.SENDGRID_API_KEY
        self._from_email = from_email or settings.SENDGRID_FROM_EMAIL

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
        idempotency_key: str | None = None,
        reply_to: str | None = None,
        custom_args: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Send email."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        payload: dict[str, Any] = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self._from_email},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": body_text},
                {"type": "text/html", "value": body_html},
            ],
        }
        if reply_to:
            payload["reply_to"] = {"email": reply_to}
        if custom_args:
            payload["personalizations"][0]["custom_args"] = custom_args

        return await self._send_with_retry(headers, payload)

    async def _send_with_retry(
        self, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(MAX_RETRIES):
                try:
                    resp = await client.post(
                        SENDGRID_API_URL, headers=headers, json=payload
                    )
                    if resp.status_code in (200, 201, 202):
                        message_id = resp.headers.get("X-Message-Id", "")
                        return {
                            "status_code": resp.status_code,
                            "message_id": message_id,
                        }
                    if resp.status_code == 429 or resp.status_code >= 500:
                        import asyncio

                        wait = RETRY_BACKOFF_FACTOR ** attempt
                        logger.warning(
                            "SendGrid %s, retrying in %ss (attempt %d/%d)",
                            resp.status_code,
                            wait,
                            attempt + 1,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(wait)
                        continue
                    return {
                        "status_code": resp.status_code,
                        "error": resp.text,
                        "message_id": "",
                    }
                except httpx.HTTPError as exc:
                    import asyncio

                    last_exc = exc
                    wait = RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(
                        "SendGrid request error, retrying in %ss: %s", wait, exc
                    )
                    await asyncio.sleep(wait)

        if last_exc:
            raise last_exc
        return {"status_code": 0, "error": "Max retries exceeded", "message_id": ""}

    async def send_sms(self, *, to: str, message: str) -> dict[str, Any]:
        """Send sms."""
        raise NotImplementedError("SendGrid does not support SMS")

    async def make_call(self, *, to: str, script: str) -> dict[str, Any]:
        """Create call."""
        raise NotImplementedError("SendGrid does not support voice calls")

    async def normalize_webhook_event(
        self, raw_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise webhook event."""
        event_type = raw_payload.get("event", "unknown")
        return {
            "event_type": event_type,
            "provider_event_id": raw_payload.get("sg_event_id", ""),
            "contact_identifier": raw_payload.get("email", ""),
            "occurred_at": raw_payload.get("timestamp", ""),
            "provider_message_id": raw_payload.get("sg_message_id", "").split(".")[0],
        }

    @staticmethod
    def verify_webhook_signature(
        payload_bytes: bytes, signature: str, timestamp: str
    ) -> bool:
        """Verify a SendGrid Event Webhook signature.

        ``SENDGRID_WEBHOOK_SECRET`` supports either a PEM ECDSA public key for
        production SendGrid verification or a legacy HMAC secret for tests and
        local fixtures. Missing configuration fails closed.
        """
        verification_key = settings.SENDGRID_WEBHOOK_SECRET
        if not verification_key:
            logger.error("SENDGRID_WEBHOOK_SECRET not set; rejecting webhook")
            return False
        if not signature or not timestamp:
            return False

        signed_payload = timestamp.encode() + payload_bytes
        if "BEGIN PUBLIC KEY" in verification_key:
            try:
                public_key = serialization.load_pem_public_key(
                    verification_key.encode()
                )
                if not isinstance(public_key, ec.EllipticCurvePublicKey):
                    logger.error("SENDGRID_WEBHOOK_SECRET is not an ECDSA public key")
                    return False
                public_key.verify(
                    base64.b64decode(signature),
                    signed_payload,
                    ec.ECDSA(hashes.SHA256()),
                )
                return True
            except (ValueError, binascii.Error, InvalidSignature):
                return False

        expected = hmac.new(
            verification_key.encode(), signed_payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
