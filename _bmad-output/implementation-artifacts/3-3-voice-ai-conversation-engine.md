# Story 3.3: Voice AI Conversation Engine

Status: ready-for-dev

## Story

As the AI voice assistant,
I want to understand speech, generate contextual responses, and speak them back,
so that I can have natural conversations with prospects following the reference script.

## Acceptance Criteria

1. **Given** audio arrives from Twilio WebSocket **When** Deepgram STT processes it **Then** speech is transcribed to text in real-time with <100ms latency
2. **Given** transcribed text is available **When** Groq LLM processes it **Then** a contextual response is generated using the voice script + conversation history in <200ms
3. **Given** LLM response text is ready **When** Deepgram TTS synthesizes it **Then** audio is generated and streamed back through the WebSocket in <100ms
4. **Given** the full pipeline runs **When** end-to-end latency is measured **Then** total round-trip (STT→LLM→TTS) is under 500ms
5. **Given** the voice script has Q&A pairs **When** the prospect asks a question in the script **Then** the AI answers using the scripted answer
6. **Given** the prospect asks a question NOT in the script **When** the AI cannot answer **Then** it uses the fallback response and logs the question in unanswered_questions
7. **Given** the prospect expresses interest in scheduling **When** the AI detects scheduling intent **Then** it asks the scheduling question from the script and records scheduling_interest=true
8. **Given** the conversation state is tracked **When** turns exceed the maximum (e.g., 20 turns) **Then** the AI wraps up the conversation politely

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/infrastructure/providers/deepgram_stt.py (AC: 1)
  - [ ] DeepgramSTTAdapter class
  - [ ] Streaming WebSocket connection to Deepgram Nova-2
  - [ ] Send raw audio chunks, receive interim/final transcription results
  - [ ] Handle connection lifecycle (open, data, close, error)
  - [ ] Config: model=nova-2, language=en, encoding=mulaw, sample_rate=8000
- [ ] Task 2: Create apps/api/app/infrastructure/providers/deepgram_tts.py (AC: 3)
  - [ ] DeepgramTTSAdapter class
  - [ ] Send text to Deepgram Aura API
  - [ ] Receive audio stream back
  - [ ] Convert to format Twilio expects (μ-law 8kHz)
  - [ ] Config: model=aura-asteria-en, encoding=mulaw, sample_rate=8000
- [ ] Task 3: Create apps/api/app/infrastructure/providers/groq_llm.py (AC: 2)
  - [ ] GroqLLMAdapter class
  - [ ] Send conversation history + system prompt to Groq API
  - [ ] Model: llama-3.1-8b-instant
  - [ ] System prompt construction: script context + conversation history + contact info + response rules
  - [ ] Response rules: stay on script, use fallback for unknown questions, detect scheduling interest
- [ ] Task 4: Create apps/api/app/domain/voice/conversation_engine.py (AC: 4,5,6,7,8)
  - [ ] ConversationEngine class managing the real-time pipeline
  - [ ] State tracking: turn_count, current_phase (greeting/pitch/qa/close), conversation_history
  - [ ] Pipeline orchestration: audio → STT → LLM → TTS → audio
  - [ ] Question matching: compare prospect question against script Q&A pairs
  - [ ] Unanswered question detection: LLM tags questions not covered by script
  - [ ] Scheduling intent detection: LLM identifies interest in meeting/demo/call
  - [ ] Max turn limit with graceful wrap-up
- [ ] Task 5: Create system prompt template (AC: 5,6,7)
  - [ ] Template incorporating: script sections, contact name/company, conversation rules
  - [ ] Rules: "If the prospect asks something not covered in the Q&A section, use the fallback response and note the question"
  - [ ] Rules: "If the prospect shows interest in meeting, ask the scheduling question"
  - [ ] Rules: "Keep responses concise — 1-2 sentences max"
- [ ] Task 6: Integrate conversation engine with Twilio WebSocket handler from Story 3.2 (AC: 4)
  - [ ] Wire audio flow: Twilio WS → STT → Engine → LLM → TTS → Twilio WS
  - [ ] Handle concurrent audio streams (full-duplex)
- [ ] Task 7: Add DEEPGRAM_API_KEY and GROQ_API_KEY to settings (AC: 1,2,3)
- [ ] Task 8: Write unit tests for conversation engine state management (AC: 5,6,7,8)
- [ ] Task 9: Write integration tests for full pipeline with mocked providers (AC: 4)

### Review Findings

- [x] [Review][Patch] Authenticate and bind Twilio media-stream WebSocket before accepting provider work [apps/api/app/api/routes/voice.py:65]
- [x] [Review][Patch] Redact provider error logging for Groq and Deepgram instead of writing raw response bodies [apps/api/app/infrastructure/providers/groq_llm.py:51, apps/api/app/infrastructure/providers/deepgram_tts.py:42]
- [x] [Review][Patch] Add fail-fast handling for missing Groq and Deepgram API keys before constructing provider Authorization headers [apps/api/app/core/config.py:105]
- [x] [Review][Patch] Await cancellation and bound cleanup for STT/LLM/TTS tasks on call drop, stop, idle timeout, and call timeout [apps/api/app/api/routes/voice.py:118]
- [x] [Review][Patch] Treat caller transcript as untrusted input and stop using free-form LLM tags as authoritative business-state controls [apps/api/app/domain/voice/conversation_engine.py:98]
- [x] [Review][Patch] Use streaming/low-latency pipeline instead of final-only STT plus full-response TTS buffering [apps/api/app/infrastructure/providers/deepgram_stt.py:40]
- [x] [Review][Patch] Enforce and measure per-stage latency budgets for STT, Groq, TTS, and total round trip [apps/api/app/api/routes/voice.py:165]
- [x] [Review][Patch] Add unit and mocked integration tests for conversation state, prompt-injection resistance, teardown, and latency-budget behavior [apps/api/tests]

Validation: `uv run pytest tests/domain/test_voice_conversation_engine.py tests/domain/test_voice_provider_safety.py tests/domain/test_voice_media_stream.py` — 14 passed, 6 warnings.

## Dev Notes

- This is the hardest story — real-time streaming audio pipeline
- Deepgram Nova-2 STT: streaming WebSocket, ~100ms latency, $0.0043/min
- Groq Llama 3.1 8B: REST API, ~150ms latency (LPU), 14,400 req/day free
- Deepgram Aura TTS: REST/streaming, ~100ms latency, $0.005/min
- Total target latency: <500ms end-to-end
- Audio format: Twilio sends μ-law 8kHz mono, we need to match this for STT and TTS
- System prompt should be concise to keep LLM latency low — avoid huge prompts

### References
- [Source: architecture.md#Section-4 — Complete Voice AI Pipeline with latency analysis]
- [Source: architecture.md#Section-8 — Deepgram STT, Deepgram TTS, Groq LLM integration boundaries]
- [Source: prd.md#FR-V3 — real-time AI conversation]
- [Source: prd.md#FR-V4 — script context and Q&A]
- [Source: prd.md#FR-V5 — unanswered question logging]
- [Source: prd.md#FR-V6 — scheduling intent detection]
- [Source: prd.md#NFR5 — voice AI <500ms latency]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
