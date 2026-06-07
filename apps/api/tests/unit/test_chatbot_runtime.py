from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.audit.audit_events import AuditEvent
from app.domain.chatbot.engine import BotRuntimeInput, ConversationEngine
from app.domain.chatbot.models import (
    ChatbotBotConfig,
    ChatbotChannelType,
    ChatbotConversation,
    ChatbotConversationStatus,
    ChatbotKnowledgeSource,
    ChatbotKnowledgeSourceType,
    ChatbotMessage,
    ChatbotMessageSender,
    ChatbotOptOut,
)
from app.domain.chatbot.prompts import disclosure_prefixed, validate_ai_disclosure
from app.infrastructure.providers.chat.base import ChatDeliveryReceipt
from app.infrastructure.rag.retriever import RetrievalResult
from app.infrastructure.vector_store.chunk_repository import RetrievedChunk


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.published: list[tuple[str, str]] = []

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, _seconds: int, value: str) -> bool:
        self.values[key] = value
        return True

    async def publish(self, channel: str, value: str) -> int:
        self.published.append((channel, value))
        return 1


class FakeAdapter:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, visitor_id: str, text: str) -> ChatDeliveryReceipt:
        self.sent.append((visitor_id, text))
        return ChatDeliveryReceipt(accepted=True, provider_message_id=f"out-{len(self.sent)}")


class FakeLlm:
    def __init__(self, response: str = "The demo is available after a short qualification call.") -> None:
        self.response = response
        self.calls = 0

    async def chat_completion(self, **_: Any) -> str:
        self.calls += 1
        return self.response


def _session() -> Session:
    _ = AuditEvent
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _input(text: str | None = "hello", *, is_text: bool = True, is_opt_out: bool = False) -> BotRuntimeInput:
    return BotRuntimeInput(
        workspace_id="ws-a",
        channel_type=ChatbotChannelType.facebook_messenger,
        visitor_id="visitor-1",
        provider_message_id=f"msg-{text or 'non-text'}-{is_text}-{is_opt_out}",
        text=text,
        is_text=is_text,
        is_opt_out=is_opt_out,
        raw_payload={"text": text},
    )


def test_disclosure_validation_rejects_empty_and_prefixes_output() -> None:
    with pytest.raises(AssertionError):
        validate_ai_disclosure("")

    reply = disclosure_prefixed("Hello", "AI assistant")

    assert reply.startswith("AI assistant")
    assert disclosure_prefixed(reply, "AI assistant") == reply


def test_engine_records_opt_out_before_rag(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail_retrieve(*_: Any, **__: Any) -> RetrievalResult:
        raise AssertionError("RAG should not run for opt-out")

    monkeypatch.setattr("app.domain.chatbot.engine.retrieve_context", fail_retrieve)

    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
            result = await ConversationEngine(session=session, adapter=adapter).process(
                _input("STOP", is_opt_out=True)
            )
            opt_out = session.exec(select(ChatbotOptOut)).first()
            conversation = session.exec(select(ChatbotConversation)).one()

            assert result.reason == "opt_out"
            assert opt_out is not None
            assert conversation.status == ChatbotConversationStatus.bot_paused
            assert "AI assistant" in adapter.sent[0][1]

    asyncio.run(scenario())


def test_engine_low_confidence_escalates_and_publishes_event(monkeypatch: pytest.MonkeyPatch) -> None:
    async def low_confidence(*_: Any, **__: Any) -> RetrievalResult:
        return RetrievalResult(chunks=[], best_confidence=0.0)

    monkeypatch.setattr("app.domain.chatbot.engine.retrieve_context", low_confidence)

    async def scenario() -> None:
        with _session() as session:
            redis = FakeRedis()
            adapter = FakeAdapter()
            session.add(
                ChatbotBotConfig(
                    workspace_id="ws-a",
                    escalation_message="I do not have that answer. A teammate can help.",
                    lead_capture_json={"confidence_threshold": 0.5},
                )
            )
            session.commit()

            result = await ConversationEngine(session=session, redis=redis, adapter=adapter).process(
                _input("unknown policy")
            )
            conversation = session.exec(select(ChatbotConversation)).one()
            bot_message = session.exec(
                select(ChatbotMessage).where(ChatbotMessage.sender == ChatbotMessageSender.bot)
            ).one()

            assert result.escalated is True
            assert conversation.status == ChatbotConversationStatus.escalated
            assert conversation.escalation_reason == "low_confidence"
            assert bot_message.bot_confidence == 0.0
            assert redis.published[0][0] == "chatbot:inbox:ws-a:events"

    asyncio.run(scenario())


def test_engine_token_cap_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        source_title="Pricing",
        content="Pricing requires a demo.",
        score=1.0,
    )

    async def high_confidence(*_: Any, **__: Any) -> RetrievalResult:
        return RetrievalResult(chunks=[chunk], best_confidence=1.0)

    monkeypatch.setattr("app.domain.chatbot.engine.retrieve_context", high_confidence)

    async def scenario() -> None:
        with _session() as session:
            session.add(ChatbotBotConfig(workspace_id="ws-a", token_cap_per_session=1))
            session.add(
                ChatbotKnowledgeSource(
                    workspace_id="ws-a",
                    source_type=ChatbotKnowledgeSourceType.faq,
                    title="Pricing",
                )
            )
            session.commit()
            llm = FakeLlm()
            result = await ConversationEngine(session=session, llm=llm, adapter=FakeAdapter()).process(
                _input("support plan details")
            )

            assert result.reason == "token_cap_reached"
            assert result.escalated is True
            assert llm.calls == 0

    asyncio.run(scenario())


def test_engine_grounded_response_records_confidence_and_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        source_title="Demo FAQ",
        content="Demos are available Tuesday through Thursday.",
        score=0.9,
    )

    async def high_confidence(*_: Any, **__: Any) -> RetrievalResult:
        return RetrievalResult(chunks=[chunk], best_confidence=0.9)

    monkeypatch.setattr("app.domain.chatbot.engine.retrieve_context", high_confidence)

    async def scenario() -> None:
        with _session() as session:
            adapter = FakeAdapter()
            result = await ConversationEngine(session=session, llm=FakeLlm(), adapter=adapter).process(
                _input("what days are tours available")
            )
            bot_message = session.exec(
                select(ChatbotMessage).where(ChatbotMessage.sender == ChatbotMessageSender.bot)
            ).one()

            assert result.reason == "bot_response"
            assert result.confidence == 0.9
            assert "AI assistant" in result.reply_text
            assert bot_message.bot_confidence == 0.9
            assert bot_message.prompt_tokens is not None
            assert bot_message.completion_tokens is not None
            assert adapter.sent[0][0] == "visitor-1"

    asyncio.run(scenario())
