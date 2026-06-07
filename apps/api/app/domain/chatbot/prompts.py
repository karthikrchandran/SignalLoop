"""Prompt construction and disclosure enforcement for ChatBot Hub."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.chatbot.models import ChatbotBotConfig
from app.infrastructure.vector_store.chunk_repository import RetrievedChunk

MIN_DISCLOSURE_LENGTH = 10
DEFAULT_INABILITY_MESSAGE = "I don't have that information. Let me connect you to someone who can help."


@dataclass(frozen=True)
class ChatHistoryTurn:
    """One conversation turn used in prompt construction."""

    role: str
    content: str


def validate_ai_disclosure(disclosure: str) -> str:
    """Return a normalized disclosure or raise when compliance text is unsafe."""
    normalized = " ".join((disclosure or "").split())
    if len(normalized) < MIN_DISCLOSURE_LENGTH:
        raise AssertionError("AI disclosure must be at least 10 characters")
    return normalized


def disclosure_prefixed(text: str, disclosure: str) -> str:
    """Ensure outbound bot text visibly includes the configured AI disclosure."""
    normalized_disclosure = validate_ai_disclosure(disclosure)
    body = (text or "").strip()
    if normalized_disclosure.lower() in body.lower():
        return body
    return f"{normalized_disclosure}\n\n{body}"


def build_system_prompt(
    *,
    bot_config: ChatbotBotConfig,
    chunks: Sequence[RetrievedChunk],
    history: Sequence[ChatHistoryTurn],
    current_message: str,
) -> str:
    """Build the grounded system prompt for one chatbot response."""
    disclosure = validate_ai_disclosure(bot_config.ai_disclosure)
    persona = (bot_config.persona or "You are a concise, helpful business assistant.").strip()
    inability = (bot_config.escalation_message or DEFAULT_INABILITY_MESSAGE).strip()
    context_lines = []
    for index, chunk in enumerate(chunks, start=1):
        context_lines.append(
            f"[Source {index}: {chunk.source_title} | score={chunk.score:.2f}]\n{chunk.content.strip()}"
        )
    context = "\n\n".join(context_lines) or "No approved knowledge base context was retrieved."
    history_text = "\n".join(f"{turn.role}: {turn.content}" for turn in history[-10:]) or "No prior turns."

    return "\n".join(
        [
            persona,
            "",
            f'You are an AI assistant. You must always identify yourself as an AI: "{disclosure}".',
            "Answer only from the provided context. Do not invent facts, prices, policies, or capabilities.",
            f'If the context does not contain the answer, say: "{inability}"',
            "",
            "[CONTEXT]",
            context,
            "",
            "[CONVERSATION HISTORY]",
            history_text,
            "",
            "[CURRENT VISITOR MESSAGE]",
            current_message.strip(),
        ]
    )

