---
workflowType: prd
date: "2026-04-02"
inputDocuments:
  - _bmad-output/planning-artifacts/product-brief-EngageHub.md
  - _bmad-output/planning-artifacts/sprint-change-proposal-2026-04-02.md
documentPurpose: "MVP requirements baseline for product, engineering, QA, and operations"
primaryAudience:
  - product_manager
  - solution_architect
  - engineering_lead
  - qa_lead
  - sre
---

# Product Requirements Document: EngageHub

## 1. Product Summary

EngageHub automates B2B outreach for lean teams through two integrated channels: multi-step email sequences and AI-powered voice cold calling. 

The product enables marketing operations admins to:
1. Define multi-step email sequences with different content per step and configurable delays
2. Upload contact lists and activate campaigns for automatic email execution
3. Create voice scripts that an AI assistant uses to make ~50 cold calls per day
4. Detect positive signals from email replies and voice call outcomes
5. Trigger appropriate followup actions automatically (followup calls after positive emails, demo links after positive calls)
6. Receive post-call summaries emailed to the team with transcripts, unanswered questions, and scheduling requests

The MVP proves the core claim: a lean marketing team can run fully automated email sequences and AI-driven cold calling at scale (50 calls/day) without daily engineering intervention.

## 2. Intended Audience for This PRD

- Product owner and product manager: scope, priorities, release gates
- Solution architect and engineering leads: capability boundaries and quality targets
- Developers: implementable functional and non-functional requirements
- QA: measurable acceptance and validation targets
- SRE or platform owner: operational controls, reliability, and observability expectations

## 3. MVP Goals

1. Enable non-technical admins to define email sequences and activate campaigns for automatic execution.
2. Execute email sequences continuously and reliably, sending followup emails on schedule with different content per step.
3. Operate an AI voice cold calling system that makes ~50 calls per day using a reference script.
4. Detect positive intent from email replies and voice call outcomes within the same operating cycle.
5. Trigger appropriate followup actions automatically (followup calls after positive emails, demo emails after positive calls).
6. Provide the team with post-call summaries, including call transcripts, unanswered questions, and scheduling requests.
7. Enforce governance constraints: daily email/call caps, timezone-aware quiet hours, consent/suppression rules.
8. Keep failures visible, recoverable, and auditable.

## 4. MVP Scope

### In scope

- Contact intake through CSV import and manual entry
- Campaign creation and audience selection
- Email sequence builder: define multi-step sequences with configurable delays and different content per step
- Email execution via SendGrid: send sequences on schedule, track delivery/open/reply status
- Voice script management: upload/edit reference scripts with question-answer sections
- AI voice calling via Twilio Voice + Deepgram STT/TTS + Groq Llama 3.1 8B
- Voice AI conversation engine: greet, pitch, answer prospect questions from script, acknowledge unanswerable questions, ask about scheduling
- Post-call automation: generate call summary, email team with transcript and unanswered questions
- Governance controls: daily email/call caps, timezone-aware quiet hours, consent/suppression enforcement, pause/resume
- Signal detection: positive email replies trigger followup actions; voice call outcomes (answered, scheduling requested) trigger actions
- Call log: review recent calls with outcome, recording playback, transcript
- Sequence progress monitor: see contacts' current step, next send time, signal status
- Operations dashboard: show emails sent/opened/replied, calls made/answered/scheduled, signals detected
- Audit log: record all operationally significant system actions and user changes

### Out of scope

- Multi-language voice support (Phase 2)
- CRM integration (Phase 2)
- Advanced analytics, A/B testing, ML scoring models (Phase 2)
- Calendar bridge for automated booking (Phase 2 — voice AI asks about scheduling; team handles booking)
- Native mobile application
- Custom ML scoring models
- Enterprise compliance packs beyond daily caps and quiet hours

## 5. User Roles

| Role | Primary responsibility | What they need from the system |
| --- | --- | --- |
| Marketing Ops Admin | Define sequences, scripts, and campaigns; operate daily | Simple sequence builder, script editor, status visibility, clear pause/resume controls |
| Revenue or RevOps Manager | Monitor outreach health and approve scale-up | Operations dashboard, KPI summaries, reliability evidence |
| Sales Engineer | Receive qualified leads and scheduling requests | Post-call email with call summary, prospect questions, scheduling status |
| System | Execute sequences and voice calls; enforce rules | Deterministic state, reliable retries, auditability, signal-triggered actions |

## 6. Core User Journeys

### Journey 1: Set up and activate an email sequence campaign

A marketing ops admin creates a multi-step email sequence (e.g., 5 steps over 14 days), imports contacts via CSV, assigns the sequence to the campaign, sets daily email caps and quiet hours, and activates the campaign. The system begins sending step 1 to all contacts at their local time within the quiet window.

### Journey 2: Operate an email sequence continuously

The admin monitors the sequence progress dashboard and sees emails sent, opens, replies, and any paused contacts. If a contact replies positively, the system pauses their sequence and triggers a followup voice call. The admin can view the call log and transcript after each interaction.

### Journey 3: Set up a voice calling campaign

A marketing ops admin uploads a reference script with Q&A sections (greeting, pitch, handling common objections, scheduling ask), configures the voice campaign to target prospects, and activates it. The system respects the daily 50-call cap and timezone-aware quiet hours.

### Journey 4: Run AI voice calls automatically

The voice AI system initiates ~50 calls per day, follows the script in real-time, answers prospect questions using the script context, acknowledges questions it cannot answer, asks about scheduling with a sales agent, and records the call. After the call, the team receives an email summary with the transcript, unanswered questions, and whether the prospect expressed scheduling interest.

### Journey 5: Detect and respond to signals

When the system detects a positive email reply, it automatically schedules a followup voice call and sends the prospect a demo links email. When the system detects a positive voice call outcome (prospect wants to schedule), it creates or flags a scheduling request for the team. The admin sees all signal-driven actions in the sequence progress monitor and call log.

### Journey 6: Scale confidently

The revenue manager reviews the operations dashboard to see email and call throughput, reply rates, call answer rates, signal detection rates, and system reliability. They determine readiness to promote the pilot to a larger ring.

## 7. Functional Requirements

### Campaign setup and content management (FR1–FR7)

- **FR1**: The system must allow a marketing ops admin to create, edit, activate, pause, and archive campaigns.
- **FR2**: The system must support CSV import and manual contact entry with required field validation.
- **FR3**: The system must validate required contact fields during import and report invalid rows with specific reasons.
- **FR4**: The system must allow contacts to be assigned to a campaign audience.
- **FR5**: The system must allow an admin to attach email sequences and voice scripts to a campaign.
- **FR6**: The system must support email sequence templates with multiple steps and different content per step.
- **FR7**: The system must support reusable personalization tokens in email templates and voice scripts (e.g., {{first_name}}, {{company_name}}).

### Governance and operating controls (FR9–FR13 simplified)

- **FR9**: The system must allow admins to set daily email send caps and daily voice call caps per campaign.
- **FR10**: The system must enforce timezone-aware quiet hours for both email and voice outreach.
- **FR11**: The system must enforce consent, suppression, and do-not-contact rules before every outbound action.
- **FR12**: The system must support campaign-level and global pause/resume controls without creating duplicate actions.
- **FR13**: The system must record who changed governance settings (pause/resume, caps, quiet hours) and when.

### Workflow execution and continuity (FR14–FR18)

- **FR14**: The system must execute email sequences automatically based on configured step delays (e.g., send step 1 on day 0, step 2 on day 3, step 3 on day 7).
- **FR15**: The system must maintain a current workflow state for each contact (e.g., current sequence step, next send time, signal status, pause reason).
- **FR16**: The system must prevent duplicate committed outreach actions across retry and recovery scenarios.
- **FR17**: The system must retry transient failures automatically with exponential backoff and surface terminal failures to operators.
- **FR18**: The system must preserve deferred work during provider outages (SendGrid, Twilio) and resume it automatically within 15 minutes of restoration.

### Email sequence execution (FR6 modified, FR14 modified)

- **FR6** (reframed): The system must support email sequence templates organized as sequential steps, each with independently configurable content, subject line, and delay from the previous step.
- **FR14** (reframed): The system must advance contacts through email sequence steps automatically based on configured delays and pause them on positive signal detection or consent/suppression triggers.

### AI voice calling (new: FR-V1 through FR-V8)

- **FR-V1**: The system must make automated outbound voice calls using an AI voice assistant powered by Twilio Voice, Deepgram real-time STT/TTS, and Groq Llama 3.1 8B LLM inference.
- **FR-V2**: The system must load and use a reference script file to guide the AI voice conversation, including greeting, pitch, question-answer sections, and scheduling ask.
- **FR-V3**: The AI voice assistant must answer prospect questions in real-time by querying the script context and generating contextual responses via the LLM.
- **FR-V4**: For questions the AI cannot confidently answer from the script context, the voice assistant must acknowledge the question and note it for team followup.
- **FR-V5**: The AI voice assistant must ask the prospect if they want to schedule a call with a sales agent or representative.
- **FR-V6**: After each call, the system must email the campaign team with a call summary including the call transcript, outcome (answered/voicemail/no-answer/busy), unanswered questions, and whether the prospect expressed scheduling interest.
- **FR-V7**: The system must enforce a daily cap of approximately 50 cold calls per campaign or globally, distributing calls throughout available hours and respecting quiet hours.
- **FR-V8**: The AI voice assistant must operate in English for Phase 1, with multi-language support planned for Phase 2 and beyond.

### Signal detection from email and voice (FR19–FR20 modified)

- **FR19** (modified): The system must detect positive signals from email replies, including reply presence, reply within 24 hours, and customizable keyword patterns.
- **FR20** (modified): The system must detect call outcomes and signals from AI voice calls, including call answer status, prospect questions asked, questions answered from script, questions requiring followup, and explicit interest in scheduling a call.

### Signal-driven actions (new: FR-S1 through FR-S2)

- **FR-S1**: When the system detects a positive or semi-positive email signal (e.g., prospect replied), it must automatically trigger two actions: (1) schedule a followup voice call within 24 hours, and (2) send a demo links or engagement email to the prospect.
- **FR-S2**: When the system detects that a prospect expressed interest in scheduling a call during an AI voice call, it must create or flag a scheduling request for the team and send a notification email with call details.

### Visibility and operations (FR24–FR25, FR31–FR34 simplified)

- **FR24**: The system must process positive signal detection and route contacts to appropriate next actions within the same operating cycle as the triggering event.
- **FR25**: The system must move leads to configured followup states (e.g., pause sequence and schedule call, send nurture email) according to signal-triggered rules.
- **FR31**: The system must provide a unified timeline for each lead, showing all sequence steps, email sends, replies, voice calls, signals detected, and actions triggered.
- **FR32**: The system must maintain an audit log of all key system actions (email sent, call initiated, signal detected, state changed) and user actions (pause campaign, adjust caps, edit sequence), including actor, timestamp, and action description.
- **FR33**: The system must show campaign health to authorized operators: queue status, contacts per step, paused contacts, detected signals, failed actions, and retry state.

## 8. Non-Functional Requirements

### Performance

- **NFR1**: Admin actions (campaign save, pause, resume, sequence edit, cap adjustment) must return visible response within 2 seconds at p95 under expected MVP load.
- **NFR2**: Dashboard views (sequence progress, call log, operations dashboard) must load within 3 seconds at p95 for normal operator queries.
- **NFR3**: Email sequence step advancement and signal detection must complete within 60 seconds at p95 from event ingestion (reply webhook, call completion webhook).
- **NFR4**: CSV import of up to 10,000 contacts must complete validation and queue acceptance within 15 minutes at p95.
- **NFR5**: Voice AI round-trip latency (speech-to-text → LLM reasoning → text-to-speech) must remain under 500ms at p95 for natural conversation flow.

### Reliability and recovery

- **NFR6**: The core workflow must achieve 99.9% monthly availability in production.
- **NFR7**: Duplicate committed outreach actions must remain at 0% in validation and production monitoring.
- **NFR8**: After provider recovery (SendGrid, Twilio, Groq, Deepgram), deferred work must resume within 15 minutes.
- **NFR9**: Terminal failures and dead-letter items (undeliverable emails, failed calls) must be visible to operators within 60 seconds.
- **NFR10**: Call recordings and transcripts must be durably stored and retrievable for at least 90 days.

### Security and compliance

- **NFR11**: All traffic must use TLS 1.2 or higher, and sensitive data (contact details, call recordings, API credentials) must be encrypted at rest.
- **NFR12**: Access control must follow least privilege; admin functions must be restricted to users with admin role.
- **NFR13**: Admin sessions must expire after a configurable idle timeout no greater than 30 minutes by default.
- **NFR14**: Provider API secrets (SendGrid, Twilio, Groq, Deepgram credentials) must be stored in managed secret storage and must never appear in plaintext logs or UI.
- **NFR15**: Consent, suppression, and do-not-contact rules must be enforced before every email send or voice call, and violations must be logged.

### Accessibility and usability

- **NFR16**: Core admin workflows (sequence builder, campaign setup, call review) must meet WCAG 2.1 AA accessibility standards.
- **NFR17**: Critical controls (pause, resume, edit) must be keyboard accessible.
- **NFR18**: The MVP must deliver a responsive web experience for desktop and mobile browser widths; native mobile app is not required.

### Operability and audit

- **NFR19**: Every operationally significant action must include actor or system identity, timestamp, action type, and correlation identifier for tracing.
- **NFR20**: Audit and timeline records must support retention for at least one year and export within two hours of a valid request.
- **NFR21**: All email deliveries, openings, replies, and bounces must be logged via SendGrid webhooks; all voice calls, transcripts, and outcomes must be logged via Twilio callbacks.

## 9. Success Criteria

### Business success

- Two marketing ops admins can define email sequences, upload contacts, activate campaigns, and operate them daily without engineering escalation.
- The product supports the weekly operating rhythm: setup on Monday, tune sequences/scripts on Wednesday, review KPIs on Friday.
- Sales team receives post-call summaries within minutes of each call, including transcript and next-action items.

### Delivery success

- **Week 1**: Email sequence engine working — admins can define multi-step sequences, activate campaigns, and send emails on schedule for 48 hours unattended.
- **Week 2**: Signal detection and followup actions working — positive email replies trigger followup calls; voice calls complete and team receives post-call summaries.
- **Week 3**: Seven-day continuous run with email and voice execution, signal detection, and automatic followup actions. Demonstrate recovery from a simulated provider outage.

### Quality success

- No duplicate committed email sends or voice calls in validation or production.
- All email deliveries, bounces, replies, and voice call outcomes are logged and visible in the timeline.
- Operators can understand why a prospect was paused, why a followup action was triggered, and when the system last attempted an action.

## 10. Release Gates

The MVP is ready for broader rollout only if all of the following are true:

1. **Sequence execution**: Admins can define a 5-step email sequence with different content per step, activate a campaign with 100+ contacts, and the system sends all steps on schedule with zero duplicates and 99%+ delivery rate.
2. **Voice calling**: The system makes ~50 voice calls per day, maintains call answer rate above 20%, and generates post-call summaries with transcripts and unanswered questions for all calls.
3. **Signal detection and followup**: Positive email signals trigger followup calls and demo emails; voice call scheduling signals are captured and flagged for the team.
4. **Governance**: Daily email and call caps are enforced; quiet hours are respected across all timezones; pause/resume controls work without creating duplicate actions.
5. **Reliability**: Pilot ring runs continuously for 7 days with <0.1% duplicate action rate, 99.9% availability, and successful recovery from at least one provider outage (SendGrid or Twilio).
6. **Operability**: Audit logs, sequence timeline, and call log are complete and auditable. Operators can troubleshoot failures and understand system state.

## 11. Open Product Decisions

These items are intentionally left open for implementation and vendor selection:

- **Voice AI latency optimization**: While Groq, Deepgram, and Twilio Media Streams target sub-500ms round-trip latency, implementation may require streaming optimizations or prompt tuning to achieve target.
- **Post-call delivery mechanism**: Whether post-call summaries are delivered via email, Slack webhook, or web dashboard (or combination).
- **Script format and parsing**: Whether scripts are stored as markdown, YAML, or JSON; how Q&A sections are parsed and indexed for LLM retrieval.
- **Call review UI sophistication**: MVP supports playback and transcript view; advanced features like call highlight tagging and compliance checking are Phase 2.
- **Demo links and nurture email content**: Whether demo links and nurture email templates are pre-provided or admin-defined; whether they're tied to offer packs or standalone templates.

These decisions must support the product brief. They must not expand MVP scope or create unnecessary operational burden.