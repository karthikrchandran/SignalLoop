"""Real-time voice AI conversation engine.

Orchestrates the STT → LLM → TTS pipeline for live phone conversations.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.domain.voice.script_parser import ScriptParsed
from app.infrastructure.providers.deepgram_stt import DeepgramSTTAdapter
from app.infrastructure.providers.deepgram_tts import DeepgramTTSAdapter
from app.infrastructure.providers.groq_llm import GroqLLMAdapter

logger = logging.getLogger(__name__)

MAX_TURNS = 20

SYSTEM_PROMPT_TEMPLATE = """You are a friendly and professional AI sales assistant on a phone call.
Your name is Alex. You work for the company making this call.

VOICE SCRIPT:
Opening pitch: {opening_pitch}

AVAILABLE Q&A (use these answers when the prospect asks related questions):
{qa_section}

RULES:
1. Keep responses concise — 1-2 sentences maximum.
2. If the prospect asks something NOT covered in the Q&A section above, say: "{fallback_response}"
   and tag your response with [UNANSWERED].
3. If the prospect mentions scheduling, a meeting, a demo, or wanting to talk more, ask: "{scheduling_question}"
   and tag your response with [SCHEDULING].
4. Be natural and conversational. Don't sound robotic.
5. The prospect's name is {contact_name} from {contact_company}.
6. Never reveal you are an AI unless directly asked.
7. If the conversation seems to be winding down, politely wrap up.
"""


@dataclass
class ConversationState:
    turn_count: int = 0
    messages: list[dict[str, str]] = field(default_factory=list)
    unanswered_questions: list[str] = field(default_factory=list)
    scheduling_interest: bool = False
    is_complete: bool = False


class ConversationEngine:
    """Manages a single phone conversation's AI pipeline."""

    def __init__(
        self,
        *,
        script: ScriptParsed,
        contact_name: str,
        contact_company: str,
    ) -> None:
        self._script = script
        self._contact_name = contact_name
        self._contact_company = contact_company
        self._state = ConversationState()
        self._stt = DeepgramSTTAdapter()
        self._tts = DeepgramTTSAdapter()
        self._llm = GroqLLMAdapter()
        self._system_prompt = self._build_system_prompt()
        self._pending_transcript = ""

    def _build_system_prompt(self) -> str:
        qa_section = ""
        for pair in self._script.qa_pairs:
            qa_section += f"Q: {pair.question}\nA: {pair.answer}\n\n"

        return SYSTEM_PROMPT_TEMPLATE.format(
            opening_pitch=self._script.opening_pitch,
            qa_section=qa_section or "No Q&A pairs provided.",
            fallback_response=self._script.fallback_response or "That's a great question. Let me have someone from our team follow up with you on that.",
            scheduling_question=self._script.scheduling_question or "Would you be open to a brief 15-minute call with one of our specialists?",
            contact_name=self._contact_name,
            contact_company=self._contact_company or "your company",
        )

    async def get_opening(self) -> str:
        """Get the opening pitch text for TTS."""
        return self._script.opening_pitch or "Hello, thanks for taking my call."

    async def process_user_speech(self, transcript: str) -> str:
        """Process transcribed user speech and generate AI response.

        Returns the response text to be synthesized via TTS.
        """
        if self._state.is_complete:
            return ""

        self._state.turn_count += 1
        self._state.messages.append({"role": "user", "content": transcript})

        if self._state.turn_count >= MAX_TURNS:
            self._state.is_complete = True
            return "Thank you so much for your time today. It was great speaking with you. Have a wonderful day!"

        response = await self._llm.chat_completion(
            system_prompt=self._system_prompt,
            messages=self._state.messages,
        )

        if not response:
            response = "I appreciate your time. Let me have someone follow up with you."

        # Check for special tags
        if "[UNANSWERED]" in response:
            response = response.replace("[UNANSWERED]", "").strip()
            self._state.unanswered_questions.append(transcript)

        if "[SCHEDULING]" in response:
            response = response.replace("[SCHEDULING]", "").strip()
            self._state.scheduling_interest = True

        self._state.messages.append({"role": "assistant", "content": response})
        return response

    async def synthesize_response(self, text: str) -> bytes:
        """Convert response text to audio."""
        return await self._tts.synthesize(text)

    @property
    def state(self) -> ConversationState:
        return self._state

    async def start_stt(self) -> None:
        await self._stt.connect()

    async def send_audio_to_stt(self, audio: bytes) -> None:
        await self._stt.send_audio(audio)

    async def close_stt(self) -> None:
        await self._stt.close()

    @property
    def stt(self) -> DeepgramSTTAdapter:
        return self._stt
