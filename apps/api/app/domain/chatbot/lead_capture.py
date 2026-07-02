"""Lead capture state machine and contact write-back for ChatBot Hub."""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotLeadCaptureState,
)
from app.domain.shared_records import service as shared_record_service
from app.domain_models import ContactPublic

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")

DEFAULT_INTENT_KEYWORDS = {
    "buy": "purchase-intent",
    "purchase": "purchase-intent",
    "pricing": "pricing-request",
    "price": "pricing-request",
    "quote": "pricing-request",
    "demo": "demo-request",
    "trial": "demo-request",
}

CONSENT_ACCEPT = {"yes", "y", "ok", "okay", "agree", "i agree", "consent", "sure"}
CONSENT_DECLINE = {"no", "n", "decline", "do not", "don't", "not now", "stop"}


@dataclass(frozen=True)
class LeadCaptureResult:
    """State-machine output for the runtime engine."""

    handled: bool
    reply_text: str | None = None
    contact_id: uuid.UUID | None = None
    intent: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_terms(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def detect_intent(text: str | None, configured_keywords: list[str] | None = None) -> str | None:
    """Detect purchase/demo/pricing intent from a visitor message."""
    normalized = _normalized_terms(text)
    for keyword, intent in DEFAULT_INTENT_KEYWORDS.items():
        if keyword in normalized:
            return intent
    for keyword in configured_keywords or []:
        normalized_keyword = str(keyword or "").strip().lower()
        if normalized_keyword and normalized_keyword in normalized:
            return normalized_keyword.replace(" ", "-")
    return None


def _consent_response(text: str | None) -> str | None:
    normalized = _normalized_terms(text)
    if any(token in normalized for token in CONSENT_DECLINE):
        return "declined"
    if any(token == normalized or token in normalized.split() for token in CONSENT_ACCEPT):
        return "accepted"
    return None


def _extract_contact_details(text: str | None) -> tuple[str | None, str | None, str | None]:
    raw = " ".join((text or "").split())
    email = EMAIL_RE.search(raw)
    phone = PHONE_RE.search(raw)
    email_value = email.group(0).lower() if email else None
    phone_value = re.sub(r"[^\d+]", "", phone.group(0)) if phone else None
    scrubbed = EMAIL_RE.sub("", raw)
    scrubbed = PHONE_RE.sub("", scrubbed)
    scrubbed = re.sub(r"\b(my name is|i am|i'm|this is|name is|email is|phone is|number is)\b", "", scrubbed, flags=re.I)
    name = " ".join(part for part in scrubbed.replace(",", " ").split() if part.isalpha())
    if len(name) < 2:
        name = None
    return name, email_value, phone_value


def _split_name(name: str | None) -> tuple[str | None, str | None]:
    if not name:
        return None, None
    parts = name.strip().split()
    if not parts:
        return None, None
    first = parts[0]
    last = " ".join(parts[1:]) or None
    return first, last


def _placeholder_email(channel_type: ChatbotChannelType, visitor_id: str) -> str:
    digest = hashlib.sha1(f"{channel_type.value}:{visitor_id}".encode()).hexdigest()[:16]
    return f"chatbot-{digest}@chatbot.local.invalid"


def _append_unique(values: list[str] | None, *items: str | None) -> list[str]:
    result = list(values or [])
    seen = set(result)
    for item in items:
        normalized = str(item or "").strip()
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    return result


class LeadCaptureStateMachine:
    """Controls lead capture transitions and Contact write-back."""

    def __init__(self, session: Session, bot_config: ChatbotBotConfig) -> None:
        self._session = session
        self._bot_config = bot_config

    @property
    def _config(self) -> dict[str, object]:
        return self._bot_config.lead_capture_json or {}

    def handle_inbound(
        self,
        *,
        conversation: ChatbotConversation,
        channel_type: ChatbotChannelType,
        visitor_id: str,
        text: str | None,
    ) -> LeadCaptureResult:
        """Advance the lead capture state if this inbound turn requires it."""
        if self._config.get("enabled") is False:
            return LeadCaptureResult(handled=False)

        if conversation.lead_capture_state == ChatbotLeadCaptureState.declined:
            return LeadCaptureResult(handled=False)

        if conversation.lead_capture_state == ChatbotLeadCaptureState.privacy_notice_prompt:
            return self._handle_privacy_notice_response(conversation, text)

        if conversation.lead_capture_state == ChatbotLeadCaptureState.collecting:
            return self._handle_contact_details(conversation, channel_type, visitor_id, text)

        intent = self._trigger_intent(conversation, text)
        if intent:
            conversation.lead_capture_state = ChatbotLeadCaptureState.privacy_notice_prompt
            conversation.lead_capture_intent = intent
            self._session.add(conversation)
            return LeadCaptureResult(handled=True, reply_text=self._privacy_notice(intent), intent=intent)

        return LeadCaptureResult(handled=False)

    def _trigger_intent(self, conversation: ChatbotConversation, text: str | None) -> str | None:
        configured = self._config.get("intent_keywords")
        keywords = [str(item) for item in configured] if isinstance(configured, list) else []
        intent = detect_intent(text, keywords)
        if not intent:
            return None
        min_turns = int(self._config.get("min_turns") or 3)
        if intent in DEFAULT_INTENT_KEYWORDS.values() or conversation.turn_count >= min_turns:
            return intent
        return None

    def _privacy_notice(self, intent: str) -> str:
        notice = str(
            self._config.get("privacy_notice_text")
            or "Before I collect your contact details, please confirm you consent to us storing your details so our team can follow up."
        ).strip()
        policy_url = str(self._config.get("privacy_policy_url") or "").strip()
        if policy_url:
            notice = f"{notice} Privacy policy: {policy_url}"
        return f"{notice}\n\nReply yes to continue or no to decline. Intent: {intent}."

    def _handle_privacy_notice_response(
        self,
        conversation: ChatbotConversation,
        text: str | None,
    ) -> LeadCaptureResult:
        response = _consent_response(text)
        if response == "accepted":
            conversation.lead_capture_state = ChatbotLeadCaptureState.collecting
            self._session.add(conversation)
            append_audit_event_to_session(
                self._session,
                event_name="chatbot_lead_consent_accepted",
                workspace_id=conversation.workspace_id,
                actor_role="visitor",
                resource_type="chatbot_conversation",
                resource_id=str(conversation.id),
                payload={"conversation_id": str(conversation.id)},
            )
            return LeadCaptureResult(
                handled=True,
                reply_text="Thanks. Please send your name and either your email address or phone number.",
            )

        if response == "declined":
            conversation.lead_capture_state = ChatbotLeadCaptureState.declined
            self._session.add(conversation)
            append_audit_event_to_session(
                self._session,
                event_name="chatbot_lead_consent_declined",
                workspace_id=conversation.workspace_id,
                actor_role="visitor",
                resource_type="chatbot_conversation",
                resource_id=str(conversation.id),
                payload={"conversation_id": str(conversation.id)},
            )
            return LeadCaptureResult(
                handled=True,
                reply_text="Understood. I will continue without collecting your contact details.",
            )

        return LeadCaptureResult(
            handled=True,
            reply_text="Please reply yes if you consent to us storing your details for follow-up, or no to decline.",
        )

    def _handle_contact_details(
        self,
        conversation: ChatbotConversation,
        channel_type: ChatbotChannelType,
        visitor_id: str,
        text: str | None,
    ) -> LeadCaptureResult:
        name, email, phone = _extract_contact_details(text)
        if not name or not (email or phone):
            return LeadCaptureResult(
                handled=True,
                reply_text="Please send your name and either an email address or phone number so our team can follow up.",
            )

        intent = conversation.lead_capture_intent or detect_intent(text, self._intent_keywords()) or "chatbot-lead"
        contact = self._upsert_contact(
            workspace_id=conversation.workspace_id,
            channel_type=channel_type,
            visitor_id=visitor_id,
            name=name,
            email=email,
            phone=phone,
            intent=intent,
        )
        conversation.lead_capture_state = ChatbotLeadCaptureState.confirmed
        conversation.shared_contact_id = contact.id
        conversation.outcome = ChatbotConversationOutcome.lead_captured
        self._session.add(conversation)
        append_audit_event_to_session(
            self._session,
            event_name="chatbot_lead_captured",
            workspace_id=conversation.workspace_id,
            actor_role="system",
            resource_type="contact",
            resource_id=str(contact.id),
            payload={
                "conversation_id": str(conversation.id),
                "channel_type": channel_type.value,
                "intent": intent,
                "has_email": bool(email),
                "has_phone": bool(phone),
            },
        )
        return LeadCaptureResult(
            handled=True,
            reply_text="Thanks, you are all set. Someone from our team will reach out shortly.",
            contact_id=contact.id,
            intent=intent,
        )

    def _intent_keywords(self) -> list[str]:
        configured = self._config.get("intent_keywords")
        return [str(item) for item in configured] if isinstance(configured, list) else []

    def _upsert_contact(
        self,
        *,
        workspace_id: str,
        channel_type: ChatbotChannelType,
        visitor_id: str,
        name: str,
        email: str | None,
        phone: str | None,
        intent: str,
    ) -> ContactPublic:
        first_name, last_name = _split_name(name)
        normalized_email = email.lower() if email else None
        normalized_phone = phone or None
        identity = normalized_email or normalized_phone or visitor_id
        contact_id = uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"emailvoice:chatbot-contact:{workspace_id}:{channel_type.value}:{identity}",
        )
        return shared_record_service.upsert_shared_contact(
            workspace_id=workspace_id,
            contact_id=contact_id,
            email=normalized_email or _placeholder_email(channel_type, visitor_id),
            first_name=first_name,
            last_name=last_name,
            company=None,
            phone=normalized_phone,
            timezone="UTC",
            source_channel=channel_type.value,
            tags_json=_append_unique(None, "chatbot-lead", channel_type.value),
            intent_json=_append_unique(None, intent),
            last_seen_at=_now(),
        )
