"""Generic SMTP email adapter.

Sends transactional email over plain SMTP / SMTPS / STARTTLS using
``aiosmtplib`` so it works against any RFC-compliant relay (Gmail, Office
365, Amazon SES SMTP, Mailgun SMTP, Mailpit/Mailcatcher for local dev …).

Configuration is passed at construction time via the keyword arguments below
or sourced from ``settings`` for single-tenant / demo mode:

    host             SMTP server hostname               (required)
    port             SMTP server port (default 587)
    username         SMTP auth username                 (optional)
    password         SMTP auth password                 (optional, encrypted)
    from_email       From: header                       (required)
    from_name        Display name                       (optional)
    use_tls          True for implicit TLS (port 465)   (default False)
    use_starttls     True for STARTTLS (port 587)       (default True)
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Any

import aiosmtplib

from app.infrastructure.providers.base import EmailAdapter
from app.infrastructure.providers.errors import ProviderConfigurationError

logger = logging.getLogger(__name__)

_DEFAULT_PORT = 587


class SmtpEmailAdapter(EmailAdapter):
    """Send email through a generic SMTP server."""

    def __init__(
        self,
        *,
        host: str,
        from_email: str,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        from_name: str | None = None,
        use_tls: bool = False,
        use_starttls: bool = True,
    ) -> None:
        if not host:
            raise ProviderConfigurationError("SMTP host is not configured")
        if not from_email:
            raise ProviderConfigurationError("SMTP from_email is not configured")
        self._host = host
        self._port = int(port) if port else _DEFAULT_PORT
        self._username = username or None
        self._password = password or None
        self._from_email = from_email
        self._from_name = from_name
        self._use_tls = bool(use_tls)
        # When implicit TLS is on, STARTTLS must be off.
        self._use_starttls = bool(use_starttls) and not self._use_tls

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a multipart email via SMTP."""
        reply_to = kwargs.get("reply_to")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = (
            f"{self._from_name} <{self._from_email}>"
            if self._from_name
            else self._from_email
        )
        msg["To"] = to
        if reply_to:
            msg["Reply-To"] = reply_to
        idempotency_key = kwargs.get("idempotency_key")
        if idempotency_key:
            # Surface idempotency hint as a Message-ID-style header for traceability.
            msg["X-Idempotency-Key"] = str(idempotency_key)

        msg.set_content(body_text or "")
        if body_html:
            msg.add_alternative(body_html, subtype="html")

        try:
            errors = await aiosmtplib.send(
                msg,
                hostname=self._host,
                port=self._port,
                username=self._username,
                password=self._password,
                use_tls=self._use_tls,
                start_tls=self._use_starttls,
                timeout=30,
            )
        except (aiosmtplib.SMTPException, OSError) as exc:
            logger.error("SMTP send failed host=%s: %s", self._host, exc.__class__.__name__)
            return {
                "status_code": 0,
                "message_id": "",
                "error": "smtp_send_failed",
            }

        message_id = msg.get("Message-Id", "") or ""
        rejected: dict[str, Any] = errors[0] if errors and errors[0] else {}
        if rejected:
            logger.warning(
                "SMTP send rejected for one or more recipients host=%s rejected_count=%d",
                self._host,
                len(rejected),
            )
            return {
                "status_code": 550,
                "message_id": message_id,
                "error": "smtp_recipients_rejected",
            }
        return {"status_code": 250, "message_id": message_id}
