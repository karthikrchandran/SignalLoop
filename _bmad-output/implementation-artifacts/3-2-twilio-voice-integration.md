# Story 3.2: Twilio Voice Integration

Status: ready-for-dev

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

- [ ] Task 1: Create apps/api/app/infrastructure/providers/twilio_voice.py (AC: 1,4,5)
  - [ ] TwilioVoiceAdapter class
  - [ ] initiate_call(call_request) → twilio_call_sid
  - [ ] Uses Twilio REST API: client.calls.create(to=phone, from_=twilio_number, url=twiml_url, status_callback=callback_url, record=True)
- [ ] Task 2: Add TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER to settings (AC: 1)
- [ ] Task 3: Create TwiML endpoint POST /api/v1/voice/twiml (AC: 2)
  - [ ] Returns TwiML XML: `<Response><Connect><Stream url="wss://host/api/v1/voice/media-stream" /></Connect></Response>`
  - [ ] Include call metadata parameters
- [ ] Task 4: Create WebSocket endpoint WS /api/v1/voice/media-stream (AC: 3)
  - [ ] Accept Twilio Media Stream WebSocket connection
  - [ ] Parse incoming media events (audio chunks in μ-law format)
  - [ ] Send audio back to Twilio in expected format
  - [ ] Handle stream start/stop/error events
  - [ ] Pass audio to/from the voice AI engine (Story 3.3)
- [ ] Task 5: Create status callback handler POST /api/v1/voice/status (AC: 4,6,7)
  - [ ] Verify Twilio request signature
  - [ ] Update CallRequest.status and CallSession based on callback status
  - [ ] Map Twilio statuses: initiated, ringing, in-progress, completed, busy, no-answer, failed
  - [ ] Set CallSession.outcome appropriately
- [ ] Task 6: Create recording callback handler POST /api/v1/voice/recording (AC: 5)
  - [ ] Store recording URL in CallSession.recording_url
- [ ] Task 7: Write unit tests for adapter (mock Twilio API) (AC: 1,4)
- [ ] Task 8: Write integration tests for TwiML and WebSocket endpoints (AC: 2,3)

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
### Debug Log References
### Completion Notes List
### File List
