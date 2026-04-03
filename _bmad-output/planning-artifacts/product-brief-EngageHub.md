---
title: "Product Brief: EngageHub"
status: "revised"
created: "2026-03-24"
updated: "2026-04-02"
revision: "v2-pivot"
primaryAudience:
  - product_owner
  - product_manager
secondaryAudience:
  - solution_architect
  - engineering_lead
  - qa_lead
  - sre
---

# EngageHub Product Brief

## One-Sentence Product Intent

EngageHub automates B2B outreach through multi-step email sequences and AI-powered cold calling, letting a marketing team set up campaigns and content while the system executes — sending emails on schedule, making voice calls using a reference script, and triggering followup actions when positive signals are detected.

## Who We Are Building For

### Primary users

- Marketing operations leads who set up email sequences, voice scripts, and contact lists
- Demand generation marketers who need automated multi-touch outreach without manual send-by-send work

### Secondary users

- Sales team members who receive post-call summaries and scheduling requests
- Revenue leaders who need visibility into email and call activity

### MVP operating model

- Two marketing operations admins configure sequences, scripts, and contacts
- The system executes email sends and AI voice calls automatically
- Sales team receives email summaries after each call with unanswered questions and scheduling requests
- Developers build and improve the product but are not involved in daily operations

## Problem Statement

Lean B2B teams can launch outbound campaigns, but they struggle with two specific execution gaps:

1. **Email followup dies after the first send.** Teams send an initial email but lack the tooling to automatically send 3-5 followup emails spaced days apart with different content. Manual followup is inconsistent and drops off.
2. **Cold calling is bottlenecked by humans.** Making 50 outbound calls per day requires a full-time person. An AI voice assistant following a reference script can handle routine cold calls, answer common questions, detect scheduling interest, and report back to the team.

The result: leads go cold because followup is manual, and calling capacity is limited by headcount.

## Product Promise

EngageHub automates the two highest-volume outreach activities:

`contact intake → email sequence execution → AI voice calling → signal detection → followup actions`

Marketing sets up the content and contacts. The system does the rest — sending emails on schedule, making calls using a script, and triggering the right followup when a prospect shows interest.

## MVP Outcome

The MVP proves one business claim: a marketing team can run automated email sequences and AI voice cold calls at 50 calls/day without manual intervention.

### Week 1

- Admin creates a multi-step email sequence with different content per step
- Emails send automatically on schedule (e.g., day 0, day 3, day 7)
- System detects email replies and pauses sequences for positive signals

### Week 2

- AI voice assistant makes cold calls following a reference script
- Voice AI answers prospect questions from the script, tables unknown questions
- After each call, team receives email with call summary and unanswered questions

### Week 3

- System triggers followup actions on positive signals (call after positive email, demo email after positive call)
- Admin can review call recordings, transcripts, and sequence progress
- Operations dashboard shows email and call activity metrics

## Success Measures

| Measure | Why it matters |
| --- | --- |
| Emails sent per day | Confirms sequence engine is executing reliably |
| Email open and reply rates | Shows whether sequence content is working |
| Calls completed per day | Confirms voice AI is hitting the 50 calls/day target |
| Call answer rate | Shows how many calls reach a live prospect |
| Positive signal rate | Measures prospects showing interest across both channels |
| Scheduling request rate | Shows how many prospects want a sales call |
| Followup action completion rate | Confirms the system reacts to signals automatically |

## Scope for MVP

### In scope

- Contact intake through CSV upload and manual entry
- Multi-step email sequence builder with different content per step and configurable delays
- Email sending via SendGrid with delivery, open, and reply tracking
- AI voice calling via Twilio Voice + Deepgram STT/TTS + Groq Llama 3.1 8B
- Voice script and knowledge base management
- Daily call cap enforcement (50 calls/day) and quiet hours
- Post-call automation: email team with call summary and unanswered questions
- Signal detection from email replies and voice call outcomes
- Automated followup triggers (positive email → schedule call; positive call → send demo email)
- Operations dashboard showing email and call metrics
- Call review screen with recording playback, transcript, and outcomes
- Sequence progress monitor

### Explicitly out of scope

- Multi-language voice support (Phase 2)
- CRM integration (Phase 2)
- Advanced analytics and A/B testing (Phase 2)
- Calendar bridge for automated booking (Phase 2 — voice AI asks about scheduling, team handles it)
- Native mobile app
- Custom ML scoring models
- Enterprise compliance packs beyond daily caps and quiet hours

## Product Principles

1. Automate execution, not just configuration. The system must send emails and make calls, not just help humans organize them.
2. AI voice quality matters. Sub-500ms latency on voice responses so calls feel natural.
3. Fail safely and visibly. Every failed email or call is logged and surfaced, never silently lost.
4. Keep the admin experience simple. Two screens to set up a campaign: define the sequence, upload contacts.
5. Cost-conscious by default. Use the cheapest reliable stack (Groq for LLM, Deepgram for STT/TTS, SendGrid free tier for email).

## Technology Decisions (Locked)

| Component | Technology | Rationale |
| --- | --- | --- |
| Email delivery | SendGrid (free tier: 100/day) | Reliable, webhook-based tracking, well-documented API |
| Voice telephony | Twilio Voice + Media Streams | Industry standard, WebSocket-based media streaming |
| Speech-to-text | Deepgram Nova-2 streaming | ~100ms latency, $0.0043/min, $200 free credit |
| LLM inference | Groq Llama 3.1 8B | ~150ms inference via LPU, near-free at 50 calls/day |
| Text-to-speech | Deepgram Aura streaming | ~100ms latency, $0.005/min |
| Backend | FastAPI (Python) | Already in place, good async support for WebSockets |
| Frontend | React + TypeScript | Already in place |
| Database | PostgreSQL + Redis | PostgreSQL for state, Redis for job queuing |

## Assumptions

1. Groq's free tier (14,400 requests/day) is sufficient for 50 calls/day at MVP scale.
2. Deepgram's $200 free credit covers several months of MVP usage.
3. SendGrid's 100 emails/day free tier is sufficient for initial sequences.
4. A well-structured voice script with Q&A sections covers 80%+ of prospect questions.
5. Email reply detection (via SendGrid webhooks) is sufficient for positive signal identification — no NLP needed.

## Constraints

1. Monthly operating cost must stay under $150 for external services at MVP scale.
2. Voice AI round-trip latency must be under 500ms for natural conversation flow.
3. Daily call cap of 50 enforced system-wide.
4. Timezone-aware quiet hours for both email and calls.
5. All call recordings stored for admin review.

## What Good Looks Like

When this brief is implemented well, a marketing lead can upload 200 contacts, set up a 5-step email sequence, upload a voice script, and press "activate." Over the next two weeks, the system sends emails on schedule, makes 50 calls per day, detects who's interested, triggers the right followup, and emails the sales team after every call with a summary of what happened and what needs human attention.
