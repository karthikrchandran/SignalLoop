"""ChatBot Hub runtime conversation engine."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session

from app.domain.audit.audit_events import append_audit_event_to_session
from app.domain.chatbot.escalation import confidence_threshold, evaluate_escalation
from app.domain.chatbot.lead_capture import LeadCaptureStateMachine
from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationOutcome,
    ChatbotConversationStatus,
    ChatbotMessage,
    ChatbotMessageDirection,
    ChatbotMessageSender,
    get_datetime_utc,
)
from app.domain.chatbot.prompts import (
    DEFAULT_INABILITY_MESSAGE,
    ChatHistoryTurn,
    build_system_prompt,
    disclosure_prefixed,
)
from app.domain.chatbot.repositories import (
    get_channel_config,
    get_or_create_bot_config,
    get_or_create_conversation,
    is_visitor_opted_out,
    list_recent_messages,
    record_opt_out,
)
from app.domain.chatbot.token_counter import TokenBudgetTracker, estimate_tokens
from app.infrastructure.providers.base import LlmAdapter
from app.infrastructure.providers.chat.base import (
    ChatChannelAdapter,
    ChatDeliveryReceipt,
)
from app.infrastructure.providers.registry import resolve_llm_adapter
from app.infrastructure.rag.retriever import retrieve_context

SESSION_TTL_SECONDS = 60 * 60 * 24
SESSION_HISTORY_LIMIT = 10
INBOX_EVENT_CHANNEL_PREFIX = "chatbot:inbox"
NON_TEXT_FALLBACK = "I can only respond to text messages here. Please send your question as text."
OPT_OUT_CONFIRMATION = "You have been opted out of chatbot replies for this channel."
TOKEN_CAP_FALLBACK = "I need to pause here because this conversation reached the configured token limit. Let me connect you to someone who can help."


@dataclass(frozen=True)
class BotRuntimeInput:
    """Normalized inbound runtime message."""

    workspace_id: str
    channel_type: ChatbotChannelType
    visitor_id: str
    provider_message_id: str
    text: str | None
    is_text: bool = True
    is_opt_out: bool = False
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BotRuntimeResult:
    """Result of processing one inbound message."""

    conversation_id: str
    handled_by_bot: bool
    escalated: bool
    reply_text: str | None
    confidence: float
    response_ms: int
    reason: str | None = None
    delivery: ChatDeliveryReceipt | None = None


class _FallbackGroundedLlm(LlmAdapter):
    """Local fallback used when no configured LLM credentials are available."""

    async def chat_completion(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.4,
        **_: Any,
    ) -> str:
        _ = (messages, max_tokens, temperature)
        marker = "[Source 1:"
        if marker in system_prompt:
            _, rest = system_prompt.split(marker, 1)
            content = rest.split("]\n", 1)[-1].split("\n\n", 1)[0].strip()
            if content:
                return content[:500]
        return DEFAULT_INABILITY_MESSAGE


def session_key(workspace_id: str, channel_type: ChatbotChannelType, visitor_id: str) -> str:
    """Return the Redis session key for one visitor conversation."""
    return f"chat:session:{workspace_id}:{channel_type.value}:{visitor_id}"


def inbox_event_channel(workspace_id: str) -> str:
    """Return the Redis pub/sub channel for inbox events."""
    return f"{INBOX_EVENT_CHANNEL_PREFIX}:{workspace_id}:events"


async def _redis_get_json(redis: Any, key: str) -> dict[str, Any]:
    if redis is None:
        return {}
    try:
        raw = await redis.get(key)
    except AttributeError:
        return {}
    if not raw:
        return {}
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


async def _redis_set_json(redis: Any, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
    if redis is None:
        return
    encoded = json.dumps(value, default=str)
    try:
        await redis.setex(key, ttl_seconds, encoded)
    except AttributeError:
        try:
            await redis.set(key, encoded, ex=ttl_seconds)
        except TypeError:
            await redis.set(key, encoded)


async def publish_inbox_event(
    redis: Any,
    *,
    workspace_id: str,
    event_type: str,
    conversation: ChatbotConversation,
    payload: dict[str, Any] | None = None,
) -> None:
    """Publish an inbox event when Redis pub/sub is available."""
    if redis is None:
        return
    event = {
        "event_type": event_type,
        "workspace_id": workspace_id,
        "conversation_id": str(conversation.id),
        "channel_type": conversation.channel_type.value,
        "visitor_id": conversation.visitor_id,
        "payload": payload or {},
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await redis.publish(inbox_event_channel(workspace_id), json.dumps(event, default=str))
    except AttributeError:
        return


class ConversationEngine:
    """Processes one normalized inbound chatbot message."""

    def __init__(
        self,
        *,
        session: Session,
        redis: Any = None,
        llm: LlmAdapter | None = None,
        adapter: ChatChannelAdapter | None = None,
    ) -> None:
        self._session = session
        self._redis = redis
        self._llm = llm
        self._adapter = adapter

    async def process(self, inbound: BotRuntimeInput) -> BotRuntimeResult:
        """Process one inbound message end-to-end."""
        started = time.perf_counter()
        bot_config = get_or_create_bot_config(inbound.workspace_id, self._session)
        conversation = get_or_create_conversation(
            inbound.workspace_id,
            self._session,
            channel_type=inbound.channel_type,
            visitor_id=inbound.visitor_id,
        )
        now = get_datetime_utc()
        conversation.turn_count += 1
        conversation.last_message_at = now
        conversation.updated_at = now
        if inbound.channel_type == ChatbotChannelType.whatsapp_business:
            conversation.customer_last_message_at = now
        self._session.add(conversation)

        inbound_row = self._record_message(
            inbound.workspace_id,
            conversation,
            direction=ChatbotMessageDirection.inbound,
            sender=ChatbotMessageSender.visitor,
            provider_message_id=inbound.provider_message_id,
            content=inbound.text,
            message_type="text" if inbound.is_text else "non_text",
            metadata={"raw_payload": inbound.raw_payload},
        )

        if inbound.is_opt_out:
            record_opt_out(
                inbound.workspace_id,
                self._session,
                channel_type=inbound.channel_type,
                visitor_id=inbound.visitor_id,
                reason="visitor_command",
                source_message_id=inbound_row.id,
            )
            conversation.bot_paused = True
            conversation.status = ChatbotConversationStatus.bot_paused
            self._session.add(conversation)
            reply = disclosure_prefixed(OPT_OUT_CONFIRMATION, bot_config.ai_disclosure)
            delivery = await self._send_and_record(conversation, inbound.visitor_id, reply, confidence=1.0)
            return self._result(conversation, True, False, reply, 1.0, started, "opt_out", delivery)

        if is_visitor_opted_out(
            inbound.workspace_id,
            self._session,
            channel_type=inbound.channel_type,
            visitor_id=inbound.visitor_id,
        ):
            conversation.bot_paused = True
            conversation.status = ChatbotConversationStatus.bot_paused
            self._session.add(conversation)
            return self._result(conversation, False, False, None, 0.0, started, "visitor_opted_out", None)

        if self._bot_disabled(inbound.workspace_id, inbound.channel_type):
            await self._escalate(conversation, reason="bot_disabled")
            return self._result(conversation, False, True, None, 0.0, started, "bot_disabled", None)

        if not inbound.is_text:
            reply = disclosure_prefixed(NON_TEXT_FALLBACK, bot_config.ai_disclosure)
            delivery = await self._send_and_record(conversation, inbound.visitor_id, reply, confidence=1.0)
            await self._update_session(inbound, conversation, reply, bot_config)
            return self._result(conversation, True, False, reply, 1.0, started, "non_text_fallback", delivery)

        lead_result = LeadCaptureStateMachine(self._session, bot_config).handle_inbound(
            conversation=conversation,
            channel_type=inbound.channel_type,
            visitor_id=inbound.visitor_id,
            text=inbound.text,
        )
        if lead_result.handled:
            reply = disclosure_prefixed(lead_result.reply_text or "", bot_config.ai_disclosure)
            delivery = await self._send_and_record(
                conversation,
                inbound.visitor_id,
                reply,
                confidence=1.0,
                metadata={"lead_capture_intent": lead_result.intent},
            )
            await self._update_session(inbound, conversation, reply, bot_config)
            return self._result(conversation, True, False, reply, 1.0, started, "lead_capture", delivery)

        token_tracker = TokenBudgetTracker(
            cap=max(1, bot_config.token_cap_per_session),
            used=max(conversation.session_token_total, await self._session_token_total(inbound)),
        )
        if token_tracker.exhausted:
            return await self._token_cap_result(inbound, bot_config, conversation, started)

        retrieval = await retrieve_context(
            inbound.workspace_id,
            self._session,
            query=inbound.text or "",
            index_version=conversation.index_version,
            limit=5,
        )
        threshold = confidence_threshold(bot_config)
        if retrieval.best_confidence < threshold:
            conversation.consecutive_low_confidence_count += 1
            reply = await self._escalation_reply(
                inbound,
                bot_config,
                conversation,
                retrieval.best_confidence,
                started,
                reason="low_confidence",
            )
            return reply

        conversation.consecutive_low_confidence_count = 0
        history = await self._history(inbound, conversation)
        system_prompt = build_system_prompt(
            bot_config=bot_config,
            chunks=retrieval.chunks,
            history=history,
            current_message=inbound.text or "",
        )
        estimated_prompt_tokens = estimate_tokens(system_prompt) + estimate_tokens(inbound.text)
        if not token_tracker.can_spend(estimated_prompt_tokens + 256):
            return await self._token_cap_result(inbound, bot_config, conversation, started)

        llm = self._llm or resolve_llm_adapter(
            self._session,
            inbound.workspace_id,
            default_factory=_FallbackGroundedLlm,
        )
        answer = await llm.chat_completion(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": inbound.text or ""}],
            max_tokens=256,
            temperature=0.2,
        )
        if not answer.strip():
            return await self._escalation_reply(
                inbound,
                bot_config,
                conversation,
                retrieval.best_confidence,
                started,
                reason="llm_empty",
            )

        reply = disclosure_prefixed(answer, bot_config.ai_disclosure)
        completion_tokens = estimate_tokens(reply)
        token_tracker.add(system_prompt, inbound.text, reply)
        conversation.session_token_total = token_tracker.used
        conversation.updated_at = get_datetime_utc()
        self._session.add(conversation)
        delivery = await self._send_and_record(
            conversation,
            inbound.visitor_id,
            reply,
            confidence=retrieval.best_confidence,
            prompt_tokens=estimated_prompt_tokens,
            completion_tokens=completion_tokens,
            metadata={"response_ms": int((time.perf_counter() - started) * 1000)},
        )
        await self._update_session(inbound, conversation, reply, bot_config)
        return self._result(
            conversation,
            True,
            False,
            reply,
            retrieval.best_confidence,
            started,
            "bot_response",
            delivery,
        )

    def _bot_disabled(self, workspace_id: str, channel_type: ChatbotChannelType) -> bool:
        channel = get_channel_config(workspace_id, self._session, channel_type)
        if not channel:
            return False
        return channel.config_json.get("bot_enabled") is False

    async def _escalation_reply(
        self,
        inbound: BotRuntimeInput,
        bot_config: ChatbotBotConfig,
        conversation: ChatbotConversation,
        confidence: float,
        started: float,
        *,
        reason: str,
    ) -> BotRuntimeResult:
        decision = evaluate_escalation(
            text=inbound.text,
            confidence=confidence,
            conversation=conversation,
            bot_config=bot_config,
        )
        message = bot_config.out_of_hours_message if decision.out_of_hours else bot_config.escalation_message
        reply = disclosure_prefixed(message or DEFAULT_INABILITY_MESSAGE, bot_config.ai_disclosure)
        await self._escalate(conversation, reason=decision.reason or reason, confidence=confidence)
        delivery = await self._send_and_record(conversation, inbound.visitor_id, reply, confidence=confidence)
        await self._update_session(inbound, conversation, reply, bot_config)
        return self._result(conversation, True, True, reply, confidence, started, decision.reason or reason, delivery)

    async def _token_cap_result(
        self,
        inbound: BotRuntimeInput,
        bot_config: ChatbotBotConfig,
        conversation: ChatbotConversation,
        started: float,
    ) -> BotRuntimeResult:
        reply = disclosure_prefixed(TOKEN_CAP_FALLBACK, bot_config.ai_disclosure)
        await self._escalate(conversation, reason="token_cap_reached")
        delivery = await self._send_and_record(conversation, inbound.visitor_id, reply, confidence=0.0)
        await self._update_session(inbound, conversation, reply, bot_config)
        return self._result(conversation, True, True, reply, 0.0, started, "token_cap_reached", delivery)

    async def _escalate(
        self,
        conversation: ChatbotConversation,
        *,
        reason: str,
        confidence: float | None = None,
    ) -> None:
        conversation.escalated = True
        conversation.status = ChatbotConversationStatus.escalated
        conversation.outcome = ChatbotConversationOutcome.escalated
        conversation.escalation_reason = reason
        conversation.updated_at = get_datetime_utc()
        self._session.add(conversation)
        append_audit_event_to_session(
            self._session,
            event_name="chatbot_conversation_escalated",
            workspace_id=conversation.workspace_id,
            actor_role="system",
            resource_type="chatbot_conversation",
            resource_id=str(conversation.id),
            payload={
                "reason": reason,
                "confidence": confidence,
                "channel_type": conversation.channel_type.value,
                "visitor_id": conversation.visitor_id,
            },
        )
        await publish_inbox_event(
            self._redis,
            workspace_id=conversation.workspace_id,
            event_type="new_escalation",
            conversation=conversation,
            payload={"reason": reason, "confidence": confidence},
        )

    def _record_message(
        self,
        workspace_id: str,
        conversation: ChatbotConversation,
        *,
        direction: ChatbotMessageDirection,
        sender: ChatbotMessageSender,
        content: str | None,
        message_type: str = "text",
        provider_message_id: str | None = None,
        confidence: float | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatbotMessage:
        row = ChatbotMessage(
            workspace_id=workspace_id,
            conversation_id=conversation.id,
            provider_message_id=provider_message_id,
            direction=direction,
            sender=sender,
            message_type=message_type,
            content=content,
            bot_confidence=confidence,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            metadata_json=metadata or {},
        )
        self._session.add(row)
        self._session.flush()
        return row

    async def _send_and_record(
        self,
        conversation: ChatbotConversation,
        visitor_id: str,
        reply: str,
        *,
        confidence: float,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatDeliveryReceipt | None:
        delivery = None
        if self._adapter:
            try:
                delivery = await self._adapter.send_message(
                    visitor_id,
                    reply,
                    customer_last_message_at=conversation.customer_last_message_at,
                )
            except TypeError:
                delivery = await self._adapter.send_message(visitor_id, reply)
        outbound = self._record_message(
            conversation.workspace_id,
            conversation,
            direction=ChatbotMessageDirection.outbound,
            sender=ChatbotMessageSender.bot,
            content=reply,
            provider_message_id=delivery.provider_message_id if delivery else None,
            confidence=confidence,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            metadata={
                **(metadata or {}),
                "delivery_status": delivery.status if delivery else "not_sent",
            },
        )
        if delivery and delivery.accepted:
            outbound.delivered_at = get_datetime_utc()
            self._session.add(outbound)
        return delivery

    async def _history(
        self,
        inbound: BotRuntimeInput,
        conversation: ChatbotConversation,
    ) -> list[ChatHistoryTurn]:
        stored = await _redis_get_json(self._redis, session_key(inbound.workspace_id, inbound.channel_type, inbound.visitor_id))
        raw_turns = stored.get("history")
        if isinstance(raw_turns, list):
            turns = [
                ChatHistoryTurn(role=str(item.get("role")), content=str(item.get("content")))
                for item in raw_turns
                if isinstance(item, dict) and item.get("content")
            ]
            if turns:
                return turns[-SESSION_HISTORY_LIMIT:]

        rows = list_recent_messages(inbound.workspace_id, self._session, conversation.id, limit=SESSION_HISTORY_LIMIT)
        return [
            ChatHistoryTurn(
                role="user" if row.sender == ChatbotMessageSender.visitor else "assistant",
                content=row.content or "",
            )
            for row in rows
            if row.content
        ]

    async def _session_token_total(self, inbound: BotRuntimeInput) -> int:
        stored = await _redis_get_json(self._redis, session_key(inbound.workspace_id, inbound.channel_type, inbound.visitor_id))
        try:
            return int(stored.get("token_total") or 0)
        except (TypeError, ValueError):
            return 0

    async def _update_session(
        self,
        inbound: BotRuntimeInput,
        conversation: ChatbotConversation,
        reply: str,
        bot_config: ChatbotBotConfig,
    ) -> None:
        key = session_key(inbound.workspace_id, inbound.channel_type, inbound.visitor_id)
        stored = await _redis_get_json(self._redis, key)
        history = stored.get("history") if isinstance(stored.get("history"), list) else []
        history = [
            *history,
            {"role": "user", "content": inbound.text or ""},
            {"role": "assistant", "content": reply},
        ][-SESSION_HISTORY_LIMIT:]
        await _redis_set_json(
            self._redis,
            key,
            {
                "conversation_id": str(conversation.id),
                "history": history,
                "token_total": conversation.session_token_total,
                "token_cap": bot_config.token_cap_per_session,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            SESSION_TTL_SECONDS,
        )

    def _result(
        self,
        conversation: ChatbotConversation,
        handled_by_bot: bool,
        escalated: bool,
        reply_text: str | None,
        confidence: float,
        started: float,
        reason: str | None,
        delivery: ChatDeliveryReceipt | None,
    ) -> BotRuntimeResult:
        return BotRuntimeResult(
            conversation_id=str(conversation.id),
            handled_by_bot=handled_by_bot,
            escalated=escalated,
            reply_text=reply_text,
            confidence=confidence,
            response_ms=int((time.perf_counter() - started) * 1000),
            reason=reason,
            delivery=delivery,
        )
