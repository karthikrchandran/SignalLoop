"""Abstract base class for notification provider adapters.

All channel integrations (SendGrid, Twilio, Mailchimp, Calendly …)
must subclass ``NotificationProviderAdapter`` and implement every method.
This enforces a uniform contract that the delivery pipeline can rely on
without knowing which provider is active for a given workspace.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class NotificationProviderAdapter(ABC):
    """Uniform async interface that every provider adapter must implement."""

    @abstractmethod
    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        body_html: str,
        body_text: str,
    ) -> dict[str, Any]:
        """Send a transactional email. Returns the provider's raw response."""

    @abstractmethod
    async def send_sms(self, *, to: str, message: str) -> dict[str, Any]:
        """Send an SMS message. Returns the provider's raw response."""

    @abstractmethod
    async def make_call(self, *, to: str, script: str) -> dict[str, Any]:
        """Initiate an outbound voice call. Returns the provider's raw response."""

    @abstractmethod
    async def normalize_webhook_event(
        self, raw_payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Normalise a provider webhook payload into a canonical event dict.

        The canonical shape must include at least:
          • ``event_type``  – e.g. ``"delivered"``, ``"bounce"``, ``"opened"``
          • ``provider_event_id`` – unique ID from the provider
          • ``contact_identifier`` – email or phone of the recipient
          • ``occurred_at`` – ISO-8601 UTC timestamp
        """
