---
date: "2026-04-02"
revision: "v2-pivot"
documentPurpose: "Delivery breakdown for the EngageHub MVP — email sequences + AI voice calling"
primaryAudience:
  - product_manager
  - engineering_lead
  - qa_lead
  - scrum_master
secondaryAudience:
  - solution_architect
  - developers
---

# EngageHub Epic Breakdown

## Delivery Approach

This plan breaks the revised product brief and PRD into implementation-ready epics and stories. The product pivot shifts from a human-operated outreach management platform to an automated email sequence + AI voice calling system.

Key technology decisions:
- Email: SendGrid (free tier: 100/day)
- Voice: Twilio Voice + Media Streams
- STT: Deepgram Nova-2 (streaming)
- LLM: Groq Llama 3.1 8B (LPU inference)
- TTS: Deepgram Aura (streaming)
- Backend: FastAPI (Python), PostgreSQL, Redis

## Epic Overview

| Epic | Goal | Effort | Why it matters |
| --- | --- | --- | --- |
| Epic 1 | Foundation cleanup and simplification | 1 day | Remove unnecessary complexity (MongoDB, PyCasbin, approvals) to unblock engine work |
| Epic 2 | Email sequence engine | 3-4 days | Automated multi-step email campaigns — the easier channel, establishes execution patterns |
| Epic 3 | AI voice calling pipeline | 4-5 days | AI voice assistant making 50 cold calls/day — the harder and more novel capability |
| Epic 4 | Signal-driven actions and admin visibility | 3-4 days | Ties both channels together with automated followup + monitoring |

## Dependencies

```
Epic 1 (cleanup) ─── must be first
    │
    ├──▶ Epic 2 (email sequences) ─── can start immediately after Epic 1
    │        │
    │        └──▶ Epic 4 (signals + visibility) ─── needs both channels
    │                     ▲
    └──▶ Epic 3 (voice pipeline) ──────┘ can start in parallel with late Epic 2
```

- Epic 1 must complete first — clears technical debt blocking new work
- Epics 2 and 3 can overlap (start Epic 3 once Epic 2 stories 2.1-2.3 are done)
- Epic 4 depends on Epics 2 and 3 for signal sources

---

## Epic 1: Foundation Cleanup and Simplification

### Outcome

Clean codebase with unnecessary complexity removed — MongoDB, PyCasbin, approval workflows, and offer-pack versioning stripped out. Ready for sequence engine and voice pipeline work.

### Stories

1. **Story 1.1: Remove MongoDB dependency**
   - Remove `motor` from pyproject.toml
   - Delete `apps/api/app/infrastructure/db/mongodb/` directory
   - Delete `apps/api/app/domain/events/mongo_schema.py`
   - Rewrite `apps/api/app/domain/audit/mongo_audit.py` → PostgreSQL JSONB `audit_events` table
   - Create Alembic migration for `audit_events` table
   - Remove MongoDB service from compose files

2. **Story 1.2: Remove PyCasbin and simplify authorization**
   - Remove `casbin` from pyproject.toml
   - Delete `apps/api/app/infrastructure/authz/` directory (enforcer.py, rbac_model.conf, bootstrap.csv)
   - Create simple role-check middleware: `if user.role != "admin": raise 403`
   - Update all route dependencies to use the new middleware
   - Remove policy routes that depended on PyCasbin

3. **Story 1.3: Remove approval workflow and simplify governance**
   - Delete `apps/api/app/api/routes/approvals.py`
   - Delete `apps/api/app/domain/policies/approval_service.py`
   - Templates publish directly with audit log (no approval gate)
   - Simplify governance to daily caps + quiet hours only
   - Remove complex policy engine, keep simple cap-check service

4. **Story 1.4: Remove legacy Items CRUD, offer-pack versioning, and out-of-scope UI**
   - Delete `apps/web/src/components/Items/` (legacy CRUD from template)
   - Remove or simplify `apps/api/app/api/routes/offer_packs.py`
   - Delete `apps/web/src/features/templates/OfferPackLibraryPage.tsx`
   - Remove out-of-scope UX screens (booking, handoff, ring-promotion)
   - Clean up unused imports and dead code

### Acceptance criteria

- Application builds and all existing tests pass without MongoDB or PyCasbin
- `docker compose up` starts only PostgreSQL, Redis, API, and web
- Authorization works with simple role check
- Audit events write to PostgreSQL JSONB

---

## Epic 2: Email Sequence Engine

### Outcome

Marketing admin can create multi-step email sequences with different content per step and configurable delays. The system sends emails automatically on schedule via SendGrid, detects replies, and pauses sequences on positive signals.

### Stories

1. **Story 2.1: Define sequence data model and migration**
   - Create SQLModel tables: `EmailSequence`, `SequenceStep`, `ContactSequenceState`, `SendRequest`, `EmailEvent`
   - Create Alembic migration
   - `EmailSequence`: campaign_id, name, active, created_by
   - `SequenceStep`: sequence_id, step_order, delay_days, subject_template, body_template
   - `ContactSequenceState`: contact_id, sequence_id, current_step, next_send_at, status (ACTIVE/PAUSED/STOPPED/COMPLETED), signal fields
   - `SendRequest`: idempotency_key, provider_message_id, status
   - `EmailEvent`: send_request_id, event_type, timestamp, raw_payload (JSONB)

2. **Story 2.2: Build sequence management API and UI**
   - API routes: CRUD for sequences, add/reorder/delete steps, assign to campaign
   - `POST /api/v1/sequences` — create sequence
   - `PUT /api/v1/sequences/{id}/steps` — add/update steps
   - `POST /api/v1/campaigns/{id}/activate` — activate campaign with sequence
   - Frontend: Sequence builder page with vertical timeline layout
   - Step configuration: subject, body, delay days, personalization tokens
   - Preview mode showing what recipient sees at each step

3. **Story 2.3: Implement SendGrid email adapter**
   - Create `apps/api/app/infrastructure/providers/sendgrid.py`
   - Send email via SendGrid v3 API (`POST /v3/mail/send`)
   - Include idempotency key, tracking headers, reply-to address
   - Handle 429/5xx with exponential backoff
   - Create SendGrid webhook handler route (`POST /api/v1/webhooks/sendgrid`)
   - Verify HMAC signature on incoming webhooks
   - Process events: DELIVERED, OPENED, BOUNCED, REPLIED, UNSUBSCRIBED
   - Write events to `EmailEvent` table

4. **Story 2.4: Build sequence execution worker**
   - Create `apps/workers/worker_app/sequence_worker.py`
   - Poll every 60s: query `ContactSequenceState` where status=ACTIVE and next_send_at <= NOW
   - For each due contact: load step template, merge contact fields, create SendRequest, call SendGrid
   - On success: advance to next step, set next_send_at = now + delay_days
   - On final step completion: set status = COMPLETED
   - On failure: retry with backoff, mark FAILED after 5 attempts
   - Enforce daily email cap and quiet hours before sending
   - Log audit event for every send

5. **Story 2.5: Implement reply detection and signal branching**
   - On REPLIED webhook from SendGrid: extract reply content
   - Simple keyword-based positive signal detection ("interested", "yes", "let's", "schedule", "demo")
   - On positive signal: set ContactSequenceState.status = PAUSED, record signal_type and signal_detected_at
   - On BOUNCED (hard): set status = STOPPED
   - On UNSUBSCRIBED: set status = STOPPED, add to suppression list
   - Emit signal-detected event for downstream automation (Epic 4)

### Acceptance criteria

- Admin can create a 5-step email sequence with different content per step
- Contacts added to campaign get emails sent on schedule (step 1 immediately, step 2 after 3 days, etc.)
- SendGrid webhooks update email event records
- Positive email reply pauses the sequence for that contact
- Bounced/unsubscribed contacts are stopped automatically
- No duplicate emails sent across retry scenarios
- Daily cap and quiet hours enforced

---

## Epic 3: AI Voice Calling Pipeline

### Outcome

System makes ~50 automated cold calls per day using an AI voice assistant. The voice AI follows a reference script, answers prospect questions, notes unanswerable questions, asks about scheduling, and emails the team a summary after each call.

### Stories

1. **Story 3.1: Script and knowledge base management**
   - Create SQLModel tables: `VoiceScript` (campaign_id, name, content, active), `CallRequest`, `CallSession`
   - Create Alembic migration
   - API routes: CRUD for scripts
   - `POST /api/v1/scripts` — create/update script
   - `GET /api/v1/scripts/{id}/preview` — parsed Q&A preview
   - Script parser: extract Opening Pitch, Q&A pairs, Fallback, Scheduling Question sections
   - Frontend: Script management page with editor + parsed Q&A preview
   - Store scripts as text/markdown in PostgreSQL

2. **Story 3.2: Twilio Voice integration**
   - Create `apps/api/app/infrastructure/providers/twilio_voice.py`
   - Outbound call initiation via Twilio REST API
   - TwiML response endpoint for Media Streams connection
   - WebSocket endpoint for Twilio Media Streams bidirectional audio
   - Handle Twilio status callbacks: initiated, ringing, answered, completed
   - Call recording via Twilio Recording API
   - Store recording URLs in CallSession record
   - Handle call outcomes: ANSWERED, VOICEMAIL, NO_ANSWER, BUSY, FAILED

3. **Story 3.3: Voice AI conversation engine**
   - Create `apps/api/app/domain/voice/` module
   - Create `apps/api/app/infrastructure/providers/deepgram_stt.py` — Deepgram Nova-2 streaming STT
   - Create `apps/api/app/infrastructure/providers/deepgram_tts.py` — Deepgram Aura streaming TTS
   - Create `apps/api/app/infrastructure/providers/groq_llm.py` — Groq Llama 3.1 8B adapter
   - Real-time pipeline: Twilio audio → Deepgram STT (streaming) → Groq LLM (with script context + conversation history) → Deepgram TTS (streaming) → audio back to Twilio
   - Conversation state tracking: turn count, current phase (greeting/pitch/QA/close)
   - Unanswered question detection: LLM tags questions not in script context
   - Scheduling intent detection: detect when prospect expresses interest
   - System prompt construction: script context + conversation history + contact info + rules
   - Target round-trip latency: <500ms

4. **Story 3.4: Call scheduling and daily cap worker**
   - Create `apps/workers/worker_app/call_worker.py`
   - Poll every 30s: check daily call count, query call queue for due contacts
   - Enforce daily cap (50 calls/day) and timezone-aware quiet hours
   - Distribute calls throughout available hours (not all at once)
   - Create CallRequest records, initiate calls via Twilio adapter
   - Track call outcomes, update CallSession records
   - Support trigger reasons: "campaign_activation", "positive_email_signal", "manual_queue"

5. **Story 3.5: Post-call automation**
   - Create `apps/workers/worker_app/postcall_worker.py`
   - On call completion: generate call summary
   - Summary includes: contact info, duration, outcome, transcript, unanswered questions, scheduling intent
   - Email team via SendGrid with formatted summary
   - If scheduling intent detected: flag for manual scheduling or create calendar placeholder
   - Update CallSession with post-call status
   - Log audit events

### Acceptance criteria

- Admin can upload/edit voice scripts with Q&A sections
- System makes outbound calls via Twilio with AI voice assistant
- Voice AI follows script, answers questions from script context, tables unknown questions
- Voice AI asks about scheduling with sales team
- Round-trip voice latency < 500ms (STT → LLM → TTS)
- Daily cap of 50 calls enforced, quiet hours respected
- Team receives email summary after each call with transcript and unanswered questions
- Call recordings stored and accessible for review

---

## Epic 4: Signal-Driven Actions and Admin Visibility

### Outcome

System reacts to positive signals from both email and voice channels with automated followup actions. Admin can monitor campaign operations, review calls, and see sequence progress through dashboards.

### Stories

1. **Story 4.1: Signal aggregation and contact state**
   - Unified contact signal state combining email and voice signals
   - Email signals: reply_positive, reply_negative, bounced, unsubscribed
   - Voice signals: answered, scheduling_requested, positive_interest, not_interested
   - Signal event store in PostgreSQL with timestamps and source channel
   - API endpoint: `GET /api/v1/contacts/{id}/signals` — return signal history

2. **Story 4.2: Automated followup triggers**
   - On positive email signal: (a) queue followup call in call_worker, (b) send demo links email via SendGrid
   - On voice call with scheduling interest: (a) create scheduling request record, (b) email sales team with details
   - On positive call without scheduling: (a) send follow-up resource email to prospect
   - Configurable trigger rules (admin can enable/disable specific triggers)
   - Audit trail for all automated actions

3. **Story 4.3: Campaign operations dashboard**
   - API endpoints for dashboard metrics:
     - `GET /api/v1/dashboard/email-metrics` — sent, delivered, opened, replied, bounced
     - `GET /api/v1/dashboard/call-metrics` — calls made, answered, voicemail, no-answer, scheduling requests
     - `GET /api/v1/dashboard/signals` — signals detected by type and channel
     - `GET /api/v1/dashboard/campaigns` — active campaigns with progress
   - Frontend: Operations dashboard with metric cards, active campaigns table, recent events feed
   - Daily call cap status (e.g., "42/50 calls made today")
   - Pause/resume controls for campaigns

4. **Story 4.4: Call review screen**
   - API endpoint: `GET /api/v1/calls` — list calls with filtering (campaign, date, outcome, signal)
   - API endpoint: `GET /api/v1/calls/{id}` — call detail with transcript, recording URL, unanswered questions
   - Frontend: Call log table with outcome, duration, signal, scheduling status
   - Call detail side panel: audio player, transcript, unanswered questions list
   - Manual followup actions: send demo email, flag for sales, pause contact sequence

5. **Story 4.5: Sequence monitor**
   - API endpoint: `GET /api/v1/sequences/{id}/progress` — contacts at each step, paused count, completed count
   - Frontend: Sequence progress view with visual timeline
   - Contact state breakdown: active, paused (signal), stopped (bounce/unsub), completed
   - Triggered followup actions view (contacts with signals and queued actions)
   - Per-contact detail: current step, next send time, signal history

### Acceptance criteria

- Positive email reply triggers followup call + demo email automatically
- Voice scheduling interest triggers team notification
- Operations dashboard shows email and call metrics on first load
- Call log allows filtering, recording playback, and transcript review
- Sequence monitor shows contact progression through steps
- All automated actions are logged in the audit trail

---

---

## Epic 5: Security Hardening and Tenant Isolation

### Outcome

Close tenant-isolation gaps and security weaknesses identified during code review. Ensure all domain service queries enforce `workspace_id` boundaries, no cross-tenant data leakage is possible even via unguessable UUIDs, and auth/authz edges are covered at the service layer.

### Stories

1. **Story 5.1: Add `workspace_id` to `ContactStateHistory` and enforce tenant filter in timeline service**
   - `ContactStateHistory` currently has no `workspace_id` column; tenant isolation relies solely on UUID unguessability.
   - Add `workspace_id` column (FK → `workspaces.id`, non-null, indexed) to `ContactStateHistory` table.
   - Create Alembic migration; backfill via join through `ContactProgression.workspace_id`.
   - Update `progression_service.py` to pass `workspace_id` when writing `ContactStateHistory` rows.
   - Update `timeline_service._fetch_state_history` to add `.where(ContactStateHistory.workspace_id == workspace_id)`.
   - Update `timeline_service.get_timeline_event_detail` `csh` branch to include `workspace_id` check.
   - Add unit tests covering cross-tenant isolation for all three `_fetch_*` helpers.

   **Acceptance criteria**
   - A `ContactStateHistory` row created in workspace A is not returned by a timeline query scoped to workspace B, even if the `contact_id` UUID is known.
   - Migration runs cleanly on the test database with no null `workspace_id` rows after backfill.
   - All three timeline fetch helpers (`_fetch_state_history`, `_fetch_contact_events`, `_fetch_routing_decisions`) have consistent `workspace_id` enforcement.

---

## Story-Writing Guidance

Each implementation story should include:

1. One clear business outcome
2. Data model changes (if any) with Alembic migration
3. API endpoints with request/response shapes
4. Frontend components and pages
5. At least one negative path or failure condition
6. Provider integration details (API keys, endpoints, error handling)
7. Audit and observability expectations

## Delivery Notes

- Epic 1 cleanup should take no more than 1 day — it's surgical removal, not rebuilding
- Epic 2 (email) is the warmup — well-understood problem, establishes the worker pattern for Epic 3
- Epic 3 (voice) is the hardest work — real-time WebSocket pipeline with multiple external services
- Epic 4 (signals + UI) ties everything together and gives admins visibility
- Playwright E2E tests should be updated incrementally with each epic
- Keep the MVP web-only — no native mobile, no CRM integration
- Monthly operating cost target: $80-130 for all external services at 50 calls/day
