# Story 3.1: Script and Knowledge Base Management

Status: ready-for-dev

## Story

As a marketing admin,
I want to create and manage voice scripts with Q&A sections,
so that the AI voice assistant can follow a reference script and answer prospect questions.

## Acceptance Criteria

1. **Given** no voice tables exist **When** the Alembic migration runs **Then** VoiceScript, CallRequest, and CallSession tables are created
2. **Given** VoiceScript model is defined **When** a script is created **Then** it has: id (UUID), campaign_id (FK), name (str), content (text), active (bool), created_by (UUID), created_at, updated_at
3. **Given** CallRequest model is defined **When** a call is queued **Then** it has: id (UUID), contact_id (FK), campaign_id (FK), voice_script_id (FK), trigger_reason (str), status (enum: QUEUED/IN_PROGRESS/COMPLETED/FAILED), scheduled_at (datetime), created_at
4. **Given** CallSession model is defined **When** a call completes **Then** it has: id (UUID), call_request_id (FK), twilio_call_sid (str), duration_seconds (int), outcome (enum: ANSWERED/VOICEMAIL/NO_ANSWER/BUSY/FAILED), recording_url (str nullable), transcript (text nullable), unanswered_questions (JSONB nullable), scheduling_interest (bool), postcall_status (str), created_at
5. **Given** I POST /api/v1/scripts with script content **When** the script is saved **Then** the system parses the content into sections: opening_pitch, qa_pairs, fallback_response, scheduling_question
6. **Given** I GET /api/v1/scripts/{id}/preview **When** I view preview **Then** I see the parsed Q&A pairs, opening pitch, and scheduling question separately
7. **Given** the Script Management page exists **When** I create a script **Then** I see a text editor and a live parsed Q&A preview panel

## Tasks / Subtasks

- [ ] Task 1: Create apps/api/app/domain/voice/ module with __init__.py (AC: all)
- [ ] Task 2: Create VoiceScript, CallRequest, CallSession SQLModel classes in apps/api/app/domain/voice/models.py (AC: 1,2,3,4)
  - [ ] VoiceScript: campaign_id, name, content, active, created_by, created_at, updated_at
  - [ ] CallRequest: contact_id, campaign_id, voice_script_id, trigger_reason, status enum, scheduled_at, created_at
  - [ ] CallSession: call_request_id, twilio_call_sid, duration_seconds, outcome enum, recording_url, transcript, unanswered_questions (JSONB), scheduling_interest (bool), postcall_status, created_at
- [ ] Task 3: Create Alembic migration for voice tables (AC: 1)
- [ ] Task 4: Create script parser in apps/api/app/domain/voice/script_parser.py (AC: 5)
  - [ ] Parse markdown-style script into sections based on headers:
    - ## Opening Pitch → opening_pitch text
    - ## Q&A → list of {question, answer} pairs
    - ## Fallback → fallback_response text
    - ## Scheduling → scheduling_question text
  - [ ] Return ScriptParsed dataclass with typed sections
- [ ] Task 5: Create CRUD routes in apps/api/app/api/routes/scripts.py (AC: 5,6)
  - [ ] POST /api/v1/scripts — create with auto-parse
  - [ ] GET /api/v1/scripts — list (filterable by campaign_id)
  - [ ] GET /api/v1/scripts/{id} — detail with raw + parsed content
  - [ ] GET /api/v1/scripts/{id}/preview — parsed sections only
  - [ ] PUT /api/v1/scripts/{id} — update content, re-parse
  - [ ] DELETE /api/v1/scripts/{id} — soft delete
- [ ] Task 6: Create Script Management frontend page (AC: 7)
  - [ ] Left panel: text editor for script content
  - [ ] Right panel: live parsed preview showing sections
  - [ ] Save and activate controls
- [ ] Task 7: Write unit tests for script parser (AC: 5)
- [ ] Task 8: Write API tests for script CRUD (AC: 5,6)

## Dev Notes

- Scripts are stored as plain text/markdown — the parser extracts structured sections for the LLM system prompt
- Script format example:
  ```
  ## Opening Pitch
  Hi, this is Alex from [Company]. I'm reaching out because...

  ## Q&A
  Q: What does your product do?
  A: We provide automated outreach solutions...

  Q: How much does it cost?
  A: Our pricing starts at...

  ## Fallback
  That's a great question. I'll make a note of it and have someone from our team follow up with details.

  ## Scheduling
  Would you be open to a brief 15-minute call with one of our specialists to discuss this further?
  ```

### References
- [Source: architecture.md#Section-4 — Voice AI Pipeline, script architecture]
- [Source: ux-design-specification.md#Section-5.4 — Script Management screen]
- [Source: prd.md#FR-V1 — voice script management]

## Dev Agent Record
### Agent Model Used
### Debug Log References
### Completion Notes List
### File List
