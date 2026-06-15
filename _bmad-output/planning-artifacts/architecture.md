---
workflowType: architecture
date: "2026-04-02"
projectName: "SignalLoop"
documentPurpose: "Reference architecture for automated email sequences and AI voice calling MVP"
primaryAudience:
  - solution_architect
  - engineering_lead
  - developers
  - sre
secondaryAudience:
  - qa_lead
  - product_manager
---

# SignalLoop MVP Architecture

## 1. Architecture Goal

This document describes the SignalLoop MVP architecture: an automated outreach system that executes multi-step email sequences and AI-powered voice cold calls.

The MVP delivers:

- **Email sequences**: Marketing users define multi-step campaigns with different content per step. The system sends emails automatically on schedule (day 0, day 3, day 7, etc.), tracks delivery and replies, and pauses sequences when positive signals arrive.
- **AI voice calling**: An AI assistant makes ~50 cold calls per day using a reference script, answers prospect questions, notes unanswerable questions for team follow-up, asks about scheduling, and emails the team a summary after each call.
- **Signal detection**: Simple positive/semi-positive/negative classification from email replies and voice call outcomes.
- **Post-call automation**: Automated email to team with call summary, unanswered questions, and scheduling requests.

This is a managed-service-first architecture prioritizing:

- speed to MVP with reliable, well-documented hosted services
- minimal self-managed complexity
- exactly-once email/call execution with audit trails
- operator-visible recovery flows

## 2. Key Architecture Principles

1. **Automate execution over configuration.** The system must send emails and make calls, not just help humans organize them.
2. **Separate business rules from provider integrations.** Sequence timing, signal detection, and branching logic live in the core. SendGrid, Twilio, Deepgram, and Groq are swappable adapters.
3. **Real-time voice AI at sub-500ms latency.** Conversation must feel natural. Groq's LPU (150ms LLM inference) + Deepgram streaming STT/TTS (100ms each) achieves this.
4. **Exactly-once delivery semantics.** Every email send and voice call is idempotent. State is persisted before executing side effects.
5. **Make every action explainable.** Every email, call, and branching decision produces a reason code or outcome visible to operators.
6. **Prefer PostgreSQL + Redis over polyglot datastores.** Simpler operations, fewer moving parts.
7. **Async job execution with retries and deduplication.** Background workers poll for due actions, execute idempotently, and record outcomes.

## 3. Logical System Components

### 3.1 Admin Web Application

A responsive single-page application for:

- Campaign and contact management (CSV upload, bulk import, manual entry)
- Email sequence definition (multi-step builder with step-by-step content, configurable delays)
- Voice script and knowledge-base management (upload/edit scripts, organize Q&A sections)
- Daily call cap and quiet-hours configuration
- Campaign operations dashboard (email/call metrics, sequence progress, signal summary)
- Call review screen (recording playback, transcript, unanswered questions, scheduling requests)

Built with React + TypeScript. Calls the backend API over HTTP/HTTPS.

### 3.2 Backend API Service

A FastAPI application that owns:

- Campaign, contact, template, and sequence state (CRUD)
- Sequence engine orchestration (determine which contacts need which step, when)
- Email outbound request formation and SendGrid integration
- Twilio Voice call orchestration and webhook handling
- Script management and AI conversation context
- Signal detection and branching logic
- Audit event recording
- API endpoints for admin UI and worker services

Runs as a stateless service. All state lives in PostgreSQL or Redis.

### 3.3 Sequence Executor Worker

A background job runner that:

- Polls PostgreSQL for contacts due for the next email sequence step
- Prepares the email (merge template content, add reply-to, set tracking headers)
- Calls SendGrid API to send
- Updates `ContactSequenceState` with send attempt, next scheduled step, and timestamp
- Handles failures, retries, and backoff
- Logs audit events for all sends

### 3.4 Call Scheduler and Executor Worker

A background job runner that:

- Polls the call queue (Redis or PostgreSQL) to find contacts due for outbound calls
- Respects daily call cap (50 calls/day system-wide) and quiet hours
- Initiates Twilio outbound calls with the voice AI pipeline webhook
- Tracks call outcomes (answered, voicemail, no-answer, busy)
- Logs call events and initiates post-call automation

### 3.5 Post-Call Automation Worker

A background job runner that:

- Subscribes to call-completion events from the call executor
- Generates a call summary (duration, outcome, recording URL, transcript, unanswered questions, scheduling intent)
- Emails the sales team with the summary
- If scheduling interest → creates a calendar invite or flags for manual scheduling

### 3.6 Provider Adapters

Isolated integration modules for:

- **SendGrid Adapter**: Email send requests, delivery tracking, bounce handling, reply webhook ingestion
- **Twilio Voice Adapter**: Outbound call initiation, Media Streams WebSocket negotiation, call status callbacks, recording storage/retrieval
- **Deepgram STT Adapter**: Real-time speech-to-text streaming over WebSocket
- **Deepgram TTS Adapter**: Real-time text-to-speech streaming, audio playback to Twilio
- **Groq LLM Adapter**: Inference calls for voice AI conversation logic, context-aware prompt assembly
- **PostgreSQL Adapter**: Campaign, sequence, contact, script, audit event persistence
- **Redis Adapter**: Call queue, session locks for deduplication, short-lived caches

### 3.7 Observability and Audit Layer

Shared capabilities used across components:

- Structured JSON logging with correlation IDs
- Metrics emission for email sent/delivered/opened/replied/bounced, calls made/answered/scheduled, queue depths, latency
- Tracing or request-to-job correlation for debugging
- Audit event recording (who did what, when, why)
- Health checks and alerting rules for provider failures, retry spikes, dead-letter queues

## 4. Voice AI Pipeline

### 4.1 Architecture

The voice AI system is a real-time conversational AI running in parallel with a live phone call. Here's the flow:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          VOICE AI PIPELINE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 1. CALL INITIATION                                                │  │
│  │    - Call Scheduler Worker triggers outbound call via Twilio API   │  │
│  │    - Twilio dials prospect number                                  │  │
│  │    - On connect, Twilio opens Media Streams WebSocket to backend   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                  │                                          │
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 2. MEDIA STREAMS WEBSOCKET (Bidirectional Audio)                  │  │
│  │    - Prospect audio arrives as 160-byte PCM chunks (~20ms each)    │  │
│  │    - Audio is streamed in real-time to Deepgram STT               │  │
│  │    - TTS audio from Deepgram is buffered and sent back to Twilio   │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                  │                                          │
│        ┌─────────────────────────┴──────────────────────────┐              │
│        ▼                                                     ▼              │
│  ┌──────────────────────────┐                    ┌──────────────────────┐  │
│  │ 3. DEEPGRAM NOVA-2 STT   │                    │ 4. AI CONVERSATION   │  │
│  │    (Streaming, ~100ms)   │                    │                      │  │
│  │                          │                    │ - Load script context│  │
│  │ - Convert prospect       │────────────────────▶ - Parse prospect turn│  │
│  │   speech to text         │   Interim trans.   │ - Generate response  │  │
│  │ - Return interim + final │◀────────────────────   using Groq LLM     │  │
│  │   transcripts (@100ms    │   Response text    │ - Route to TTS       │  │
│  │   latency)               │                    │                      │  │
│  └──────────────────────────┘                    └──────┬───────────────┘  │
│                                                         │                  │
│                                                         │ Response text    │
│                                                         │                  │
│                                                         ▼                  │
│                                              ┌──────────────────────────┐  │
│                                              │ 5. DEEPGRAM AURA TTS    │  │
│                                              │    (Streaming, ~100ms)  │  │
│                                              │                        │  │
│                                              │ - Stream TTS audio      │  │
│                                              │ - Send to Twilio Media  │  │
│                                              │   Streams (~100ms)      │  │
│                                              └──────────────────────────┘  │
│                                                         │                  │
│                                                         ▼                  │
│                                              ┌──────────────────────────┐  │
│                                              │ TWILIO MEDIA STREAMS     │  │
│                                              │ (Back to Caller)         │  │
│                                              └──────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 6. CONVERSATION STATE & MEMORY                                      │  │
│  │    - Track turn count, duration, prosody/sentiment signals         │  │
│  │    - Record unanswered questions for team follow-up                │  │
│  │    - Detect scheduling intent ("yes, I'd like to schedule")        │  │
│  │    - Generate call transcript (from STT stream + turn records)      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 7. CALL COMPLETION                                                  │  │
│  │    - Prospect hangs up or 6-minute timeout (safety limit)          │  │
│  │    - Groq returns final turn with closing action                    │  │
│  │    - Twilio call ends, recording is saved                          │  │
│  │    - Call worker publishes call-completed event                    │  │
│  │    - Post-call worker generates team summary email                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Latency and Throughput

**Total round-trip latency target: <500ms per exchange**

- Prospect speaks: ~100-500ms (variable)
- Deepgram STT streaming: ~100ms (incremental transcription)
- Groq LLM inference: ~150ms (Llama 3.1 8B on LPU)
- Deepgram TTS streaming: ~100ms (first audio chunk)
- Network + buffer: ~50ms

**Total: ~500ms of perceived latency per exchange.** This creates natural pauses that feel like the AI is "thinking."

**Throughput**:
- ~50 concurrent calls max (Twilio default, can be increased)
- Daily cap: 50 calls/day per policy, not resource limitation
- Expected cost: ~$62/month (Twilio $14 + Deepgram $43 + Groq ~$5) at 50 calls/day

### 4.3 Script Architecture

Voice scripts are stored as Markdown or plain text in PostgreSQL. The format supports:

```
# Welcome
Hello [prospect_name]. This is [agent_name] from [company_name]. 
Do you have a quick minute to talk about [topic]?

# Pitch
We help [industry] teams [problem_solved].

## FAQ
Q: How does your product work?
A: [explanation]

Q: What's the price?
A: Starting at [price]. Can I schedule a quick demo?

## Closing
If interested: "Great, let me have our team set up a time to show you a demo."
If not: "No problem. I'll have our team send you some resources."
```

The Groq prompt includes:

1. System instruction: "You are an AI sales assistant following this script..."
2. Script context (relevant sections)
3. Conversation history (last 3-5 turns)
4. Prospect name and company context (from contact record)
5. Current conversation state (greeting vs. pitch vs. Q&A vs. close)

On unknown questions, the LLM is instructed to say: *"That's a great question. Let me have our team follow up on that with you."* and move to scheduling.

### 4.4 Call Recording and Transcript

- **Recording**: Twilio stores call recordings; backend retrieves via API after completion
- **Transcript**: Built from STT interim/final transcripts captured during the call + manually assembled into ordered turn structure
- **Storage**: Both stored in cloud (AWS S3 or similar) with signed URLs for playback in admin UI

## 5. Email Sequence Engine

### 5.1 Architecture

The email sequence engine automates multi-step campaigns with timing:

```
┌───────────────────────────────────────────────────────────────────────┐
│                     EMAIL SEQUENCE ENGINE                             │
├───────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 1. SEQUENCE DEFINITION (Admin Creates)                      │  │
│  │                                                             │  │
│  │  EmailSequence:                                            │  │
│  │    - campaign_id                                           │  │
│  │    - active (boolean)                                      │  │
│  │    - created_by_user_id                                    │  │
│  │    - created_at / updated_at                               │  │
│  │                                                             │  │
│  │  SequenceStep[] (ordered list):                             │  │
│  │    - step_order (1, 2, 3, ...)                             │  │
│  │    - template_id (which email content)                     │  │
│  │    - delay_days (0, 3, 7, 14, ...)                         │  │
│  │    - subject_template ("Follow up: [company_name]")        │  │
│  │    - body_template (merge fields + dynamic content)        │  │
│  │    - pause_on_reply (boolean) — detect signal?             │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 2. CONTACT ASSIGNMENT                                        │  │
│  │                                                             │  │
│  │  For each contact added to campaign:                        │  │
│  │    - Create ContactSequenceState record                    │  │
│  │    - current_step = 1                                       │  │
│  │    - next_send_at = NOW (step 1 sends immediately)         │  │
│  │    - status = "ACTIVE"                                      │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 3. STEP SCHEDULER WORKER (Periodic Polling)                │  │
│  │                                                             │  │
│  │  Every 1-5 min (configurable):                              │  │
│  │    1. Query: ContactSequenceState where                    │  │
│  │       - status = 'ACTIVE'                                  │  │
│  │       - next_send_at <= NOW                                │  │
│  │      (limit 100 per batch)                                 │  │
│  │                                                             │  │
│  │    2. For each contact:                                     │  │
│  │       a. Load sequence step definition                     │  │
│  │       b. Load template content                             │  │
│  │       c. Merge contact fields ([CONTACT_NAME], etc.)       │  │
│  │       d. Prepare email with idempotency key                │  │
│  │       e. Create SendRequest record (before send)           │  │
│  │       f. Call SendGrid API                                 │  │
│  │       g. Update ContactSequenceState                       │  │
│  │          - current_step += 1                               │  │
│  │          - next_send_at = NOW + delay_days                │  │
│  │          - last_sent_at = NOW                              │  │
│  │          - status stays 'ACTIVE' unless signal             │  │
│  │       h. Log audit event                                   │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 4. SENDGRID WEBHOOK HANDLER                                │  │
│  │                                                             │  │
│  │  SendGrid fires webhooks for each email event:             │  │
│  │    - DELIVERED: Contact received email                    │  │
│  │    - OPENED: Contact opened email                         │  │
│  │    - CLICKED: Contact clicked link (not tracked initially) │  │
│  │    - BOUNCED: Email failed (hard/soft)                    │  │
│  │    - MARKED_AS_SPAM: Contact flagged as spam              │  │
│  │    - UNSUBSCRIBED: Contact clicked unsub                  │  │
│  │    - REPLIED: Contact sent reply (if webhook enabled)     │  │
│  │                                                             │  │
│  │  On each event:                                             │  │
│  │    1. Verify HMAC signature (SendGrid webhook auth)        │  │
│  │    2. Log event (EmailEvent record)                        │  │
│  │    3. Update contact signal state                          │  │
│  │    4. If BOUNCED + hard: mark unsendable               │  │
│  │    5. If REPLIED: check for positive signal               │  │
│  │    6. If signal detected: pause sequence, trigger followup│  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 5. SIGNAL DETECTION                                         │  │
│  │                                                             │  │
│  │  On REPLIED event:                                          │  │
│  │    - Extract reply content                                 │  │
│  │    - Check for positive keywords (see table below)        │  │
│  │    - If positive signal found:                             │  │
│  │      a. Set ContactSequenceState.status = 'PAUSED'        │  │
│  │      b. Record signal_detected_at and signal_type         │  │
│  │      c. Emit signal-detected event (for automation)       │  │
│  │      d. Log audit event                                    │  │
│  │    - If negative/unsubscribe:                              │  │
│  │      a. Set status = 'STOPPED'                            │  │
│  │      b. Log reason (bounce, unsubscribe, spam)            │  │
│  │                                                             │  │
│  │  Simple signal classification:                             │  │
│  │    POSITIVE: "interested", "yes", "let's", "call", time   │  │
│  │    NEGATIVE: "not interested", "remove", "stop"           │  │
│  │    NEUTRAL: everything else                               │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │ 6. AUTOMATED FOLLOWUP TRIGGERS                             │  │
│  │                                                             │  │
│  │  When positive signal detected from email:                  │  │
│  │    1. Queue outbound call (add to call scheduler queue)    │  │
│  │    2. Schedule demo links email (separate SendRequest)     │  │
│  │    3. Notify sales team (email with contact + signal)      │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                      │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Model for Sequences

**EmailSequence**
- `id` (UUID, PK)
- `campaign_id` (FK)
- `name` (string, e.g., "Initial Outreach Campaign")
- `description` (text)
- `active` (boolean)
- `created_by_user_id` (FK, audit)
- `created_at`, `updated_at` (timestamps)

**SequenceStep**
- `id` (UUID, PK)
- `sequence_id` (FK)
- `step_order` (int, 1-N)
- `template_id` (FK referencing template/email content)
- `delay_days` (int, 0 for immediate)
- `subject_template` (string with merge fields)
- `body_template` (string, HTML or plain)
- `pause_on_reply` (boolean, should we stop sequence if reply detected?)

**ContactSequenceState**
- `id` (UUID, PK)
- `contact_id` (FK)
- `sequence_id` (FK)
- `current_step` (int, 1 = first step)
- `next_send_at` (timestamp)
- `status` (enum: ACTIVE, PAUSED, STOPPED, COMPLETED)
- `signal_detected_at` (timestamp, nullable)
- `signal_type` (enum: POSITIVE, SEMI_POSITIVE, NEGATIVE, null)
- `signal_source` (string: "email_reply", "call_outcome", etc.)
- `completed_at` (timestamp, nullable, when all steps sent)
- `created_at`, `updated_at`

**SendRequest** (idempotency + audit)
- `id` (UUID, PK)
- `contact_sequence_state_id` (FK)
- `sequence_step_id` (FK)
- `idempotency_key` (unique, UUID per step per contact)
- `provider` (string: "sendgrid")
- `status` (enum: PENDING, SENT, FAILED, DEFERRED)
- `provider_message_id` (string from SendGrid API, nullable if not sent)
- `created_at`, `sent_at` (timestamp)
- `error_message` (string, nullable)

**EmailEvent** (webhook tracking)
- `id` (UUID, PK)
- `send_request_id` (FK)
- `event_type` (enum: DELIVERED, OPENED, BOUNCED, REPLIED, MARKED_AS_SPAM, UNSUBSCRIBED, CLICKED)
- `timestamp` (when SendGrid says it happened)
- `raw_payload` (JSONB, full webhook data for debugging)
- `processed_at` (when we ingested this event)

## 6. Workers Architecture

The background job layer consists of three independent worker services:

### 6.1 Sequence Worker (Email)

**Responsibility**: Execute scheduled email sequence steps.

**Polling interval**: Every 60 seconds.

**Process**:
1. Query: `ContactSequenceState` where `status = 'ACTIVE'` AND `next_send_at <= NOW()`
2. For each contact (batch of 100):
   - Load sequence definition and current step
   - Load contact record (email, name, etc.)
   - Load template/body content
   - Build email with merge fields
   - Create `SendRequest` record (before executing)
   - Call `SendGrid.send()` API
   - On success: update `SendRequest.provider_message_id`, `status = SENT`
   - On failure: update `SendRequest.status = FAILED`, log error
   - On success: advance `ContactSequenceState` to next step and set `next_send_at`
   - Emit audit event
3. Sleep and repeat

**Retries**: If SendGrid returns 429/5xx, defer for exponential backoff. After 5 retries, mark as FAILED and alert.

**Exactly-once**: Idempotency key ensures SendGrid rejects duplicate sends if worker restarts mid-send.

### 6.2 Call Scheduler and Executor Worker

**Responsibility**: Schedule and initiate voice calls. Maintain daily cap. Track call outcomes.

**Polling interval**: Every 30 seconds.

**Process**:
1. Check daily call counter (how many calls queued/in-progress/completed today)
2. If < 50: query call queue (Redis or PostgreSQL `CallRequest` table) for next due contact
3. For each call:
   - Check if contact opted in, not in quiet hours
   - Create call session record (CallSession with unique session_id)
   - Call `Twilio.initiate_outbound_call()` with webhook URL
   - Store in-progress call state in Redis or PostgreSQL
   - Twilio connects and opens Media Streams WebSocket
   - Voice AI pipeline begins (see section 4)
4. On call completion (Twilio webhook):
   - Update CallSession with outcome (answered, no-answer, voicemail, etc.)
   - Extract final transcript from STT
   - Record unanswered questions
   - Detect if scheduling interest detected
   - Emit call-completed event
   - Trigger post-call worker

**Call queue**: Can be a simple `CallRequest` table with `status` (QUEUED, IN_PROGRESS, COMPLETED) or a Redis list with deduplication.

**Quiet hours**: Enforce timezone-aware quiet hours (e.g., no calls 5pm–9am, no calls on weekends). Store quiet hours config per contact or globally.

**Exactly-once**: Idempotency key in Twilio API prevents duplicate call initiations if worker restarts.

### 6.3 Post-Call Automation Worker

**Responsibility**: Generate and send team summaries after calls. Handle scheduling requests.

**Trigger**: Listens to call-completed events (webhook from voice pipeline or polling).

**Process**:
1. On call-completed event:
   - Load CallSession record
   - Generate summary email body:
     ```
     Contact: [name] ([company])
     Duration: [minutes]
     Outcome: [answered/voicemail/no-answer]
     Recording: [link to playback]
     Transcript: [full transcript]
     Key Questions Unanswered:
       - [question 1]
       - [question 2]
     Scheduling Intent: [yes/no/unclear]
     Next Action: [queue demo email / follow up manually / etc.]
     ```
   - Send email to configured team addresses (e.g., sales@company.com)
   - If scheduling intent detected:
     - Create calendar invite or flag in CRM
     - Send note to sales team about scheduling request
   - Emit automation-completed event
   - Log audit event

**Delivery**: Idempotent — if worker crashes mid-send, next retry will still find the same event and can deduplicate (store processed event IDs).

## 7. Data Model

### 7.1 Core Domain Objects

**Campaign**
- `id`, `name`, `description`
- `owner_user_id`, `created_at`, `updated_at`
- `status` (ACTIVE, PAUSED, COMPLETED, ARCHIVED)

**Contact**
- `id`, `campaign_id`
- `email`, `phone` (optional, for voice)
- `first_name`, `last_name`, `company`
- `contact_metadata` (JSONB for custom fields)
- `opted_in` (boolean)
- `created_at`, `updated_at`

**Template** (email body + subject)
- `id`, `campaign_id`
- `name`, `subject`, `body` (HTML or plain)
- `merge_fields` (JSONB: ["CONTACT_NAME", "COMPANY", ...])
- `created_at`, `version_number`

**EmailSequence**
- `id`, `campaign_id`
- `name`, `active`
- `steps` (referenced via SequenceStep table)

**SequenceStep**
- `id`, `sequence_id`
- `step_order`, `template_id`, `delay_days`

**ContactSequenceState**
- `id`, `contact_id`, `sequence_id`
- `current_step`, `next_send_at`
- `status` (ACTIVE, PAUSED, STOPPED, COMPLETED)
- `signal_detected_at`, `signal_type`, `signal_source`

**SendRequest** (idempotency envelope)
- `id`, `contact_sequence_state_id`
- `idempotency_key`, `status`, `provider_message_id`

**EmailEvent** (webhook tracking)
- `id`, `send_request_id`
- `event_type`, `timestamp`, `raw_payload` (JSONB)

**VoiceScript**
- `id`, `campaign_id`
- `name`, `content` (text/markdown)
- `active`
- `created_at`, `updated_at`

**CallRequest**
- `id`, `contact_id`, `sequence_id` (nullable if standalone call)
- `status` (QUEUED, IN_PROGRESS, COMPLETED, FAILED)
- `scheduled_for` (timestamp)
- `trigger_reason` (string: "positive_email_signal", "manual_queue", etc.)

**CallSession**
- `id`, `call_request_id`
- `session_id` (Twilio/internal correlation)
- `started_at`, `ended_at`
- `outcome` (ANSWERED, VOICEMAIL, NO_ANSWER, BUSY, FAILED)
- `duration_seconds`
- `transcript` (text)
- `unanswered_questions` (JSONB array)
- `scheduling_intent` (enum: YES, NO, UNCLEAR)
- `recording_url` (S3 or Twilio URL)

**AuditEvent**
- `id`
- `user_id`, `actor_type` (USER, SYSTEM)
- `action` (EMAIL_SENT, CALL_INITIATED, SIGNAL_DETECTED, etc.)
- `resource_id`, `resource_type`
- `details` (JSONB)
- `created_at`

### 7.2 State Machines

**ContactSequenceState.status**:
```
ACTIVE --[on positive signal]--> PAUSED
ACTIVE --[on bounce/unsubscribe]--> STOPPED
ACTIVE --[after final step]--> COMPLETED
PAUSED --[manual resume]--> ACTIVE
STOPPED --[cannot transition]--> END
```

**CallSession.outcome**:
```
(Determined by Twilio and voice AI logic)
ANSWERED → (voice AI engaged, call ongoing)
NO_ANSWER → (nobody picked up)
VOICEMAIL → (left message or detected voicemail)
BUSY → (line was busy)
FAILED → (Twilio error or network issue)
```

## 8. Integration Boundaries

### 8.1 Email (SendGrid)

**Outbound**:
- POST `/v3/mail/send` — single send or batch send
- Request includes: to, from, subject, html, reply_to, headers (including custom tracking headers), merge tags
- Response: 202 ACCEPTED with message_id

**Inbound (Webhooks)**:
- Webhook POST from SendGrid for: delivered, opened, bounced, marked_as_spam, unsubscribed, replied
- Signature: HMAC-SHA256 verification on request body

**Error handling**:
- 4xx: Invalid request (validation error, unverified sender, etc.) → log and do not retry
- 5xx/429: Server error or rate limit → exponential backoff + alert

### 8.2 Telephony (Twilio Voice)

**Outbound**:
- POST `/v1/Accounts/{ACCOUNT_SID}/Calls` — initiate outbound call
- Request: To (E.164 phone), From (verified number), Url (webhook endpoint for TwiML/Media Streams)
- Response: 201 with Call SID and status

**Media Streams**:
- WebSocket upgrade to `wss://media.twilio.com/audio`
- Server receives/sends audio chunks (160 bytes, 8kHz, 16-bit PCM)
- Twilio sends events: StreamStarted, StreamData, StreamDone

**Callbacks**:
- Webhook POST for: call initiated, ringing, answered, completed
- Includes Call SID, duration, recording SID, outcome

**Recording**:
- Recordings stored by Twilio, retrievable via `/v1/Accounts/{ACCOUNT_SID}/Recordings/{RECORDING_SID}`
- Download as audio/wav or media+metadata

**Error handling**:
- 429: Rate limit → backoff
- Invalid phone number → log error, mark contact as invalid
- Network disconnects → automatic retry (up to 3 times)

### 8.3 Speech-to-Text (Deepgram Nova-2 Streaming)

**Connection**:
- WebSocket to `wss://api.deepgram.com/v1/listen`
- Header: `Authorization: Token {API_KEY}`
- Query params: `model=nova-2`, `encoding=linear16`, `sample_rate=8000`, `interim_results=true`

**Streaming**:
- Client sends: 160-byte chunks of PCM audio (from Twilio Media Streams)
- Server responds: JSON with interim transcript + confidence, final transcript when speech pause detected

**Pricing**: ~$0.0043/minute, with $200 free credit

**Error handling**:
- WebSocket disconnect → reconnect and resume (Twilio re-streams audio)
- Partial transcripts ignored; final transcripts assembled into turn history

### 8.4 Text-to-Speech (Deepgram Aura Streaming)

**Connection**:
- WebSocket to `wss://api.deepgram.com/v1/speak`
- Header: `Authorization: Token {API_KEY}`
- Query params: `model=aura-asteria-en`, `encoding=linear16`, `sample_rate=8000`

**Streaming**:
- Client sends: Text to speak (one sentence or paragraph at a time)
- Server responds: Audio chunks (160-byte PCM) streamed back

**Buffering**:
- Audio chunks buffered in application layer, sent to Twilio Media Streams as they arrive
- Target latency: <100ms to first audio chunk

**Pricing**: ~$0.005/minute

**Error handling**:
- Timeout: If no audio in 5 seconds, send fallback: "Let me have our team get back to you on that."

### 8.5 LLM Inference (Groq Llama 3.1 8B)

**API Call**:
- POST `/openai/v1/chat/completions` (OpenAI-compatible API)
- Request: messages (system prompt + conversation history), temperature, max_tokens
- Response: choices[0].message.content (the AI's response)

**Prompt Structure**:
```
System:
  "You are an AI sales assistant calling prospects about [product].
   Follow this script and knowledge base:
   [SCRIPT_CONTENT]
   
   Rules:
   - Answer questions only from the script context
   - If asked about something not in the script, say:
     'That's a great question. Let me have our team follow up on that.'
   - Ask about scheduling: 'Would you like to schedule a call with our team?'
   - Keep responses under 2 sentences
   - Be friendly and natural"

User turns:
  "Hi, who is this?" → [previous bot response]
  "How does it work?" → [previous bot response]
  "What's the price?" → [current user input - prospect speaking]
```

**Parsing response**:
- Extract text completion
- Check for "schedule" keyword to detect scheduling intent
- Extract questions marked with "Q:" for unanswered tracking
- Pass response to Deepgram TTS

**Fallback**: If Groq times out (>5 sec), send default: "I didn't catch that. Can you say it again?"

**Pricing**: Free tier = 14,400 requests/day (enough for 50 calls at ~5 exchanges per call). ~$150/month if below free tier overages.

### 8.6 PostgreSQL State Storage

**Connection pooling**: PgBouncer or application-level connection pooling (e.g., SQLAlchemy + psycopg2).

**Important patterns**:
- All operations are idempotent (INSERT OR IGNORE patterns, transaction isolation)
- Audit trail: every write generates an AuditEvent
- JSONB fields for flexible metadata (`contact_metadata`, `raw_payload`)

### 8.7 Redis Short-Lived State

**Use cases**:
- Call queue (FIFO list of next contacts to call)
- Session locks (prevents duplicate processing if workers run on multiple replicas)
- Rate limit counters (calls/day, emails/day)
- Temporary conversation session state (during live call)

**TTL**: Short-lived (1-24 hours). Persistent state in PostgreSQL.

## 9. Security Baseline

### 9.1 Authentication & Authorization

- **Admin auth**: API requires JWT token (issued on login)
- **Role check**: User must have `role = ADMIN` or equivalent
- **API keys for worker services**: Separate service account with limited scopes (e.g., call_executor role)
- **Provider credentials**: Stored in managed secret store (AWS Secrets Manager, Vault, or similar), never in code/env

### 9.2 Data Protection

- **TLS everywhere**: All traffic encrypted (HTTP → HTTPS, WebSocket → WSS)
- **Encryption at rest**: PostgreSQL at-rest encryption (AWS RDS encryption, etc.)
- **Audit events**: All user actions logged with timestamp, user_id, action, resource_id
- **Sensitive fields**: Email addresses and phone numbers should not be logged in plain text in audit

### 9.3 Provider Integration Security

- **SendGrid**: HMAC signature verification on webhooks
- **Twilio**: TLS for all API calls; webhook signature verification via X-Twilio-Signature header
- **Deepgram/Groq**: API key in Authorization header over HTTPS

### 9.4 Consent and Governance

- **Opt-in tracking**: Check `contact.opted_in` before every email/call
- **Suppression list**: Maintain global and campaign-level suppression lists
- **Unsubscribe handling**: On SendGrid unsubscribe webhook, mark contact as opted-out
- **Quiet hours**: Enforce timezone-aware quiet hours (configurable globally, overridable per contact)
- **Daily caps**: Enforce 50 calls/day, email volume limits per campaign

## 10. Observability and Operations

### 10.1 Logging

**Structured JSON logs** with correlation IDs:

```json
{
  "timestamp": "2026-04-02T14:30:45Z",
  "level": "INFO",
  "service": "sequence_worker",
  "correlation_id": "uuid-12345",
  "action": "send_email",
  "contact_id": "contact-uuid",
  "sequence_step": 1,
  "status": "sent",
  "sendgrid_message_id": "msg-uuid",
  "duration_ms": 234
}
```

**Log targets**:
- Stdout (container logs, CloudWatch, etc.)
- Centralized log aggregator (ELK, Splunk, CloudWatch Logs)

### 10.2 Metrics

**Key metrics to emit**:

*Email channel*:
- `emails_sent_total` (counter)
- `emails_delivered_total` (counter)
- `emails_opened_total` (counter)
- `emails_replied_total` (counter)
- `emails_bounced_total` (counter)
- `email_send_latency_ms` (histogram)
- `sequence_step_duration_seconds` (histogram)

*Voice channel*:
- `calls_initiated_total` (counter)
- `calls_answered_total` (counter)
- `calls_voicemail_total` (counter)
- `calls_no_answer_total` (counter)
- `calls_scheduled_total` (counter)
- `call_duration_seconds` (histogram)
- `call_ltency_ms` (histogram, round-trip speech-to-response)

*Queue health*:
- `sequence_queue_depth` (gauge)
- `call_queue_depth` (gauge)
- `retry_queue_depth` (gauge)
- `worker_batch_size` (histogram)

*System health*:
- `sendgrid_api_errors_total` (counter, by error type)
- `twilio_api_errors_total` (counter)
- `deepgram_errors_total` (counter)
- `groq_errors_total` (counter)

**Alerting rules**:
- Queue depth >100 for >30 min
- Email send success rate <95%
- Call answer rate <50%
- SendGrid API error rate >5%
- Worker restart frequency >2 per hour
- PostgreSQL connection pool exhausted
- Redis OOM warning

### 10.3 Tracing

**Correlation IDs**: Every request/job initiated by a user or system event gets a correlation_id. All downstream calls include it in logs and span tags.

**Distributed tracing**: Optional (Phase 2) — use OpenTelemetry + Jaeger or Datadog to trace request-to-job-to-provider-response.

### 10.4 Dashboards

**Operations dashboard** (for SRE/ops):
- Email metrics: sent, delivered, opened, replied, bounced (24h trends)
- Call metrics: initiated, answered, voicemail, scheduled (24h trends)
- Queue health: sequence queue depth, call queue depth, retry queue
- Error rates: SendGrid, Twilio, Deepgram, Groq
- Worker health: restarts, latency, batch sizes
- Alerts: active firing alerts

**Admin dashboard** (for marketing ops):
- Campaign overview: total contacts, active sequences, signals detected
- Email sequence: progress through steps, paused contacts, bottlenecks
- Voice: calls made today, calls scheduled, top unanswered questions
- Next actions: contacts awaiting followup, scheduling requests pending

## 11. Deployment Model

### 11.1 Recommended AWS Architecture (for hosted MVP)

**Compute**:
- Backend API: Elastic Container Service (ECS) or App Runner (2-4 instances for HA)
- Workers: ECS or Lambda (periodic trigger via EventBridge every 60 sec for sequence worker, 30 sec for call workers)
- Frontend: S3 + CloudFront (static site, React build artifacts)

**Data**:
- PostgreSQL: RDS (Multi-AZ, automated backups, encryption at rest)
- Redis: ElastiCache (cluster mode for HA)

**Secrets**:
- AWS Secrets Manager (SendGrid API key, Twilio account SID, Deepgram API key, Groq API key)

**Observability**:
- Logs: CloudWatch Logs
- Metrics: CloudWatch Metrics
- Alerting: CloudWatch Alarms + SNS + email/Slack

**Storage**:
- Call recordings: S3 with versioning + lifecycle policies
- Database backups: RDS automated backups + S3 exports

### 11.2 Alternative: Docker Compose for Local Development

For dev/test environments, use docker-compose with:
```yaml
services:
  api:
    image: myregistry/signalloop-api:latest
    ports: ["8001:8001"]
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/signalloop
  
  sequence_worker:
    image: myregistry/signalloop-workers:latest
    command: python -m workers.sequence_worker
    
  call_worker:
    image: myregistry/signalloop-workers:latest
    command: python -m workers.call_worker
    
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
  
  redis:
    image: redis:7
  
  web:
    image: myregistry/signalloop-web:latest
    ports: ["5173:80"]
```

## 12. Implementation Notes

### 12.1 Minimal Viable First Slice

To get end-to-end execution working quickly:

1. **Day 1**: Set up database schema (Campaign, Contact, EmailSequence, SequenceStep, ContactSequenceState, SendRequest, VoiceScript tables)
2. **Days 2-3**: Build sequence engine (create sequence, add contact to campaign, test step scheduler polling, test SendGrid send)
3. **Days 4-5**: Add voice pipeline (Twilio integration, test call initiation + WebSocket connection)
4. **Days 6-7**: Add voice AI (Groq LLM + Deepgram STT/TTS integration, test real Q&A)
5. **Days 8-9**: Add signal detection and post-call automation
6. **Days 10-11**: Build admin UI (sequence builder, script manager, call review, operations dashboard)
7. **Days 12-14**: Testing, error handling, observability, deployment setup

**Success criteria for Slice 1**:
- Marketing user can create an email sequence and upload contacts
- System sends emails on schedule
- Marketing user can create a voice script
- System makes ~5 test calls with voice AI answering questions
- All actions logged with audit trail

### 12.2 Cost Estimation (Monthly, 50 calls/day scale)

| Service | Usage | Cost |
|---------|-------|------|
| SendGrid | 5000 emails/month | ~$10 (free tier: 100/day) |
| Twilio Voice | ~1500 calls/month | ~$14 (per-call + per-minute) |
| Deepgram STT | ~2-3 hours/day | ~$43 (free $200 credit covers ~2 months) |
| Deepgram TTS | ~2-3 hours/day | (same Deepgram credit)  |
| Groq API | ~7500 inferences/month | Free (14,400 req/day) |
| AWS RDS (postgres) | 1 db.t3.micro | ~$30 |
| AWS ElastiCache (Redis) | cache.t3.micro | ~$15 |
| AWS ECS/App Runner | 2 backend instances | ~$50-100 |
| AWS CloudFront (frontend) | minimal | ~$5 |
| **Total** | **~$167-190/month** | All external services + infrastructure |

### 12.3 Extensibility Points (Phase 2+)

- **Multiple languages**: Groq supports multilingual models; Deepgram covers 40+ languages
- **CRM integration**: Add webhook to Salesforce/HubSpot when signal detected or call completed
- **A/B testing**: Template variants per step, measure open/reply rates, recommend best content
- **Calendar integration**: Instead of "I'll have the team follow up," AI can check sales calendar and schedule directly
- **Custom ML scoring**: Replace simple keyword matching with ML-based signal classification
- **Advanced analytics**: Funnel analysis, cohort retention, attribution to marketing campaigns

## 13. Architecture Readiness Assessment

The architecture is ready for implementation when the team commits to:

1. **Managed-service-first deployment** (AWS, cloud databases, hosted endpoints — not self-managed Kubernetes)
2. **Exact idempotency protection** (every email/call has an idempotency key, status is checked before retrying)
3. **Audit and observability as first-class citizens** (every action logged, metrics emitted from day one)
4. **Simple signal detection** (positive/negative from keywords, not complex ML)
5. **Voice AI latency constraint** (<500ms round-trip for natural conversation)

**These commitments reduce implementation scope, cut deployment burden, and align directly with the product brief.**

---

*Last revised: 2026-04-02*
*Status: Ready for sprint planning and developer handoff*