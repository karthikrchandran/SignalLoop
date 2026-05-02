# Story 3.2: Twilio Voice Integration

Status: done

## Story

As a backend engineer,
I want to integrate Twilio Voice for outbound calling and media streaming,
so that the AI voice assistant can make phone calls and exchange audio in real-time.

## Acceptance Criteria

1. **Given** a CallRequest exists **When** the Twilio adapter initiates a call **Then** an outbound call is placed via Twilio REST API to the contact's phone number
2. **Given** a call is answered **When** Twilio connects **Then** it sends a TwiML response that connects to our WebSocket endpoint for Media Streams
3. **Given** Twilio Media Streams connects **When** audio flows **Then** bidirectional audio is exchanged via WebSocket (μ-law 8kHz from Twilio, PCM back to Twilio)
4. **Given** a call is in progress **When** Twilio fires status callbacks **Then** call state is updated: initiated, ringing, answered, completed
5. **Given** a call is answered **When** recording is enabled **Then** Twilio records the call and provides a recording URL in the callback
6. **Given** a call reaches voicemail **When** the outcome is detected **Then** CallSession.outcome is set to VOICEMAIL and no AI conversation is attempted
7. **Given** a call is not answered **When** timeout occurs **Then** CallSession.outcome is set to NO_ANSWER or BUSY based on Twilio status

## Tasks / Subtasks

- [x] Task 1: Create apps/api/app/infrastructure/providers/twilio_voice.py (AC: 1,4,5)
  - [x] TwilioVoiceAdapter class
  - [x] initiate_call(call_request) → twilio_call_sid
  - [x] Uses Twilio REST API: client.calls.create(to=phone, from_=twilio_number, url=twiml_url, status_callback=callback_url, record=True)
- [x] Task 2: Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to settings (AC: 1)
- [x] Task 3: Create TwiML endpoint POST /api/v1/voice/twiml (AC: 2)
  - [x] Returns TwiML XML: `<Response><Connect><Stream url="wss://host/api/v1/voice/media-stream" /></Connect></Response>`
  - [x] Include call metadata parameters
- [x] Task 4: Create WebSocket endpoint WS /api/v1/voice/media-stream (AC: 3)
  - [x] Accept Twilio Media Stream WebSocket connection
  - [x] Parse incoming media events (audio chunks in μ-law format)
  - [x] Send audio back to Twilio in expected format
  - [x] Handle stream start/stop/error events
  - [x] Pass audio to/from the voice AI engine (Story 3.3)
- [x] Task 5: Create status callback handler POST /api/v1/voice/status (AC: 4,6,7)
  - [x] Verify Twilio request signature
  - [x] Update CallRequest.status and CallSession based on callback status
  - [x] Map Twilio statuses: initiated, ringing, in-progress, completed, busy, no-answer, failed
  - [x] Set CallSession.outcome appropriately
- [x] Task 6: Create recording callback handler POST /api/v1/voice/recording (AC: 5)
  - [x] Store recording URL in CallSession.recording_url
- [x] Task 7: Write unit tests for adapter (mock Twilio API) (AC: 1,4)
- [x] Task 8: Write integration tests for TwiML and WebSocket endpoints (AC: 2,3)

### Review Findings

- [x] [Review][Patch] Media Streams WebSocket accepts unauthenticated callers [apps/api/app/api/routes/voice.py:65]
- [x] [Review][Patch] Callback signature verification uses only the global Twilio auth token despite workspace-specific call credentials [apps/api/app/infrastructure/providers/twilio_voice.py:72]
- [x] [Review][Patch] Voicemail detection is not implemented and the AI conversation starts for every stream [apps/api/app/api/routes/voice.py:87]
- [x] [Review][Patch] Twilio lifecycle callbacks do not persist initiated, ringing, answered, or in-progress states [apps/api/app/api/routes/voice.py:229]
- [x] [Review][Patch] Call SID/session idempotency is not enforced at the database boundary [apps/api/app/domain/voice/models.py:64]
- [x] [Review][Patch] Media Streams malformed-frame, stream error, and teardown paths can leak tasks or save partial state after failure [apps/api/app/api/routes/voice.py:103]
- [x] [Review][Patch] Raw Twilio provider error bodies are logged/returned and can be persisted by workers without sanitization [apps/api/app/infrastructure/providers/twilio_voice.py:67]
- [x] [Review][Patch] Required Twilio adapter, callback, WebSocket, signature, and duplicate-delivery tests are absent [apps/api/tests:1]

## Dev Notes

- Twilio Media Streams sends audio as base64-encoded μ-law 8kHz mono
- Our WebSocket needs to be production-grade — handle disconnections, timeouts
- Twilio request signature validation is critical for security on all callback endpoints
- Use twilio Python SDK for REST API calls and signature validation
- WebSocket handler will be the glue between Twilio audio and the AI engine (Story 3.3)

### References
- [Source: architecture.md#Section-4 — Voice AI Pipeline steps 1-2 and 6-7]
- [Source: architecture.md#Section-8 — Twilio Voice integration boundary]
- [Source: prd.md#FR-V2 — outbound call via Twilio]
- [Source: prd.md#FR-V3 — real-time conversation]

## Dev Agent Record
### Agent Model Used
GitHub Copilot

### Debug Log References
- Focused pytest: `python -m pytest apps/api/tests/api/routes/test_voice_twilio.py -v --rootdir=apps/api`
- Focused Ruff: `python -m ruff check apps/api/app/api/routes/voice.py apps/api/app/infrastructure/providers/twilio_voice.py apps/api/app/domain/voice/models.py apps/workers/worker_app/call_worker.py apps/api/app/workers/call_worker.py apps/api/tests/api/routes/test_voice_twilio.py`

### Completion Notes List
- Added tenant-aware Twilio webhook signature verification that rejects unsigned requests and resolves per-workspace Twilio voice credentials by AccountSid.
- Bound Media Streams to signed call/account tokens, validated start metadata, handled malformed/error frames, and awaited teardown before saving conversation state.
- Persisted Twilio account/status lifecycle metadata, voicemail outcomes, recording URLs, and idempotency constraints for one CallSession per CallRequest plus unique non-empty Twilio CallSid.
- Sanitized Twilio provider errors and worker audit/log output so raw provider bodies and phone numbers are not exposed.
- Added focused Twilio adapter, callback, TwiML, WebSocket, tenant-signature, voicemail, recording, and duplicate/stale-delivery regression tests.

### File List
- apps/api/app/api/routes/voice.py
- apps/api/app/infrastructure/providers/twilio_voice.py
- apps/api/app/domain/voice/models.py
- apps/api/app/alembic/versions/i4d5e6f7a8b9_add_twilio_call_session_idempotency.py
- apps/workers/worker_app/call_worker.py
- apps/api/app/workers/call_worker.py
- apps/api/tests/api/routes/test_voice_twilio.py
