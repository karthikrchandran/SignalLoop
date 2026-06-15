# Sprint Change Proposal: MVP Redefinition — Email Sequences + AI Voice Calling

**Date**: 2026-04-02
**Project**: SignalLoop
**Triggered by**: Product owner strategic pivot
**Scope classification**: Major — fundamental replan required
**Mode**: MVP Redefinition + selective rollback

---

## 1. Issue Summary

### Problem Statement

The current SignalLoop plan builds a **human-operated outreach management platform** — admins configure campaigns, a queue dispatches actions, and humans interpret results. After 9 days of development, the system can configure campaigns but cannot send a single email or make a single call.

The product owner's actual need is an **automated outreach execution system** with two functional channels:

1. **Email sequences** — multi-step drip campaigns that automatically send followup emails with different content at each step until a positive signal is received
2. **AI voice assistant** — an automated caller making ~50 cold calls per day using a reference script, answering prospect questions, logging unanswerable questions for team followup, asking about scheduling with a sales agent, and emailing the team a summary after each call

### What Changed

| Dimension | Current Plan | Actual Need |
|---|---|---|
| Email execution | Queue-based single-action dispatch | Automated multi-step sequence with timing and different content per step |
| Voice/calling | Human makes calls, system tracks outcomes | AI voice assistant makes calls autonomously using a script |
| Signal handling | Rule-based classification engine | Simple: positive reply → trigger followup call + demo email |
| Booking | Calendar bridge with formal booking workflow | "Would you like to schedule a call with our team?" — asked live by voice AI |
| Handoff | Formal context packet generation | Post-call email to sales team with summary + unanswered questions |
| Governance | PyCasbin RBAC, formal approval workflow, multi-policy engine | Daily caps + quiet hours. That's it for Phase 1. |
| Datastores | PostgreSQL + MongoDB + Redis | PostgreSQL + Redis. Drop MongoDB. |
| Language | English only (implicit) | English Phase 1, multi-language Phase 2+ |

### Evidence

- Zero email sending capability implemented after 9 days
- Zero voice/telephony capability in architecture, PRD, or code
- 49 API endpoints built, none for execution
- Architecture says "telephony adapter" but means human call tracking, not AI calling
- MongoDB added as 3rd datastore for audit events — PostgreSQL JSONB handles this
- PyCasbin RBAC engine added for a 2-admin pilot — simple role check suffices

---

## 2. Impact Analysis

### Epic Impact

| Current Epic | Status | Decision | Rationale |
|---|---|---|---|
| Epic 1: Foundation | done | **Keep 70%** | Auth, deployment, config infrastructure is useful. Remove PyCasbin, MongoDB, approval workflow. |
| Epic 2: Campaign Setup | in-progress | **Restructure** | Campaign/contact/template core stays. Add sequence step concept. Drop offer-pack versioning, formal policy engine. |
| Epic 3: Outreach Execution | backlog | **Replace entirely** | Queue-dispatch model → email sequence engine + AI voice pipeline |
| Epic 4: Signal Detection | backlog | **Simplify** | Voice AI handles live signal detection. Email reply detection stays simple. |
| Epic 5: Booking & Handoff | backlog | **Simplify to post-call actions** | No formal booking workflow. Voice AI asks about scheduling. Post-call email replaces handoff packet. |
| Epic 6: Timeline/Audit/KPI | dropped | **Defer to Phase 2** | Not needed for functional Phase 1 |

### Story Impact

**Stories to keep as-done**: 1-1 (project setup), 1-2 (campaign intake — needs sequence step addition), 1-3 (template library — repurpose for sequence content)

**Stories to gut/simplify**: 1-4 (governance — strip to caps + quiet hours only), 2-1 through 2-4 (in-progress — keep contact progression, drop formal outbox/action-queue complexity)

**Stories to drop**: All of 3-x, 4-x, 5-x as currently written — they're designed for a different product

**Stories to create**: See new epic structure below

### Artifact Conflicts

| Artifact | Sections Affected | Change Type |
|---|---|---|
| Product Brief | Product promise, scope, principles, success measures | Rewrite |
| PRD | FR6-FR8 (templates→sequences), FR14 (execution model), FR19-FR25 (intent→voice outcomes), FR26-FR30 (booking→scheduling), new voice AI FRs | Major revision |
| Architecture | Remove MongoDB, PyCasbin. Add LLM pipeline, voice AI components, sequence engine | Major revision |
| Epics | Complete restructure to 4 new epics | Replace |
| UX Spec | Add script management, call review, sequence builder. Remove offer-pack library, complex governance. | Major revision |

### Technical Impact — New Technology Requirements

| Capability | Technology | Purpose |
|---|---|---|
| Email sending | SendGrid API (or equivalent) | Send sequence emails, track delivery/opens/replies |
| Voice calling | Twilio Voice API | Initiate outbound calls, manage call flow |
| Speech-to-text | Deepgram Nova-2 (streaming) | Transcribe prospect speech in real-time (~$0.0043/min, $200 free credit) |
| Text-to-speech | Deepgram Aura (streaming) | Voice AI speaks to prospect (~$0.005/min) |
| Conversational AI | Groq Llama 3.1 8B (LPU inference) | Process prospect questions against script, generate responses (~$0.001/min, 14,400 req/day free) |
| Call recording | Twilio Recording | Store call recordings for review |
| Email notifications | SendGrid (same) | Post-call summaries to sales team |

---

## 3. Recommended Approach

### Selected Path: MVP Redefinition + Selective Rollback

**Keep** the useful infrastructure:
- FastAPI backend framework
- React/TypeScript frontend
- PostgreSQL database
- Redis for job queuing
- Campaign, contact, and template domain models
- User authentication (simplified)
- Alembic migration infrastructure
- Basic API structure

**Remove** the over-engineering:
- MongoDB (event store → PostgreSQL JSONB)
- PyCasbin RBAC (→ simple `user.role` check)
- Formal approval workflow
- Policy engine complexity (keep caps + quiet hours only)
- Offer-pack versioning
- Legacy Items CRUD from template
- Out-of-scope UX screens

**Add** the core capabilities:
- Email sequence engine with step timing
- AI voice calling pipeline
- Script/knowledge base management
- Post-call automation (email summary, unanswered questions)
- Signal-driven branching (positive signal → followup call + demo email)

### Effort Estimate

| Work Block | Effort | Risk |
|---|---|---|
| Simplification/rollback | 1 day | Low |
| Email sequence engine | 3-4 days | Low — well-understood problem |
| AI voice pipeline (Twilio + Deepgram + Groq) | 4-5 days | Medium — real-time voice AI, mitigated by Groq's low latency |
| Signal detection + branching | 2 days | Low |
| Post-call automation | 1-2 days | Low |
| Admin UI for sequences + scripts + call review | 3-4 days | Low |
| **Total** | **~14-18 days** | Medium overall |

### Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Voice AI latency makes calls feel unnatural | Low | Groq LPU delivers ~150ms LLM inference + Deepgram streaming STT/TTS = ~350ms total round-trip |
| Twilio Voice costs at 50 calls/day | Low | ~$62/month at MVP scale (Twilio $14 + Deepgram $43 + Groq ~$5) |
| LLM hallucination on prospect questions | Medium | Constrain to script context only, "I'll have our team follow up" fallback |
| Email deliverability issues | Low | Use proper SPF/DKIM/DMARC setup with SendGrid |

---

## 4. Proposed New Epic Structure

### Epic 1: Foundation Cleanup and Simplification (1 day)

**Outcome**: Clean codebase with unnecessary complexity removed, ready for engine work.

| Story | Description |
|---|---|
| 1.1 | Remove MongoDB dependency — migrate audit events to PostgreSQL JSONB `audit_events` table |
| 1.2 | Remove PyCasbin — replace with simple role-check middleware using `user.role` |
| 1.3 | Remove formal approval workflow — templates publish directly with audit log |
| 1.4 | Remove legacy Items CRUD, out-of-scope UX screens, and offer-pack versioning complexity |

### Epic 2: Email Sequence Engine (3-4 days)

**Outcome**: Marketing admin can create multi-step email sequences and the system sends them automatically on schedule.

| Story | Description |
|---|---|
| 2.1 | **Define sequence data model** — `EmailSequence` (campaign_id, steps[], active), `SequenceStep` (order, template_id, delay_days, subject, body), `ContactSequenceState` (contact_id, sequence_id, current_step, next_send_at, status) |
| 2.2 | **Build sequence management API + UI** — CRUD for sequences, add/reorder steps, assign template content per step, preview |
| 2.3 | **Implement SendGrid email adapter** — send email via API, track delivery webhooks (delivered, opened, bounced, replied) |
| 2.4 | **Build sequence execution worker** — polls for contacts due for next step, sends email, advances state, handles failures/retries |
| 2.5 | **Implement reply detection and signal branching** — on positive reply: pause sequence, trigger followup call + send demo email. On bounce/unsubscribe: stop sequence. |

### Epic 3: AI Voice Calling Pipeline (5-7 days)

**Outcome**: System makes ~50 automated cold calls per day using an AI voice assistant that follows a script, answers questions, and handles scheduling.

| Story | Description |
|---|---|
| 3.1 | **Script/knowledge base management** — upload/edit script files (markdown/text), parse into Q&A sections, store in PostgreSQL, admin UI for script management |
| 3.2 | **Twilio Voice integration** — outbound call initiation, TwiML/Media Streams for real-time audio, call status callbacks, recording storage |
| 3.3 | **Voice AI conversation engine** — Twilio Media Streams WebSocket → Deepgram Nova-2 streaming STT → Groq Llama 3.1 8B (with script context) → Deepgram Aura streaming TTS → audio back to caller. Handle: greeting, pitch delivery, Q&A from script, "let me have our team follow up on that" for unknown questions, "would you like to schedule a call with our sales team?" |
| 3.4 | **Call scheduling and daily cap worker** — schedule 50 calls/day respecting quiet hours, manage call queue, track call outcomes (answered, voicemail, no-answer, busy) |
| 3.5 | **Post-call automation** — generate call summary, list unanswered questions, email team post-call. If prospect wants scheduling → create calendar invite or flag for manual scheduling. |

### Epic 4: Signal-Driven Actions and Admin Visibility (3-4 days)

**Outcome**: System reacts to signals from both channels and admin can see what's happening.

| Story | Description |
|---|---|
| 4.1 | **Signal aggregation** — combine email signals (reply sentiment, open patterns) and voice signals (call outcome, scheduling request) into unified contact signal state |
| 4.2 | **Automated followup triggers** — on positive/semi-positive signal: (a) queue followup call if from email channel, (b) send demo links email if from voice channel, (c) notify sales team |
| 4.3 | **Campaign operations dashboard** — show: emails sent/opened/replied per sequence step, calls made/answered/scheduled, active sequences, signal summary |
| 4.4 | **Call review screen** — list recent calls with outcome, recording playback, transcript, unanswered questions, scheduling status |

---

## 5. Detailed Change Proposals

### 5.1 Product Brief Changes

**OLD** (Product Promise):
> SignalLoop gives a small business team a reliable operating loop:
> `lead intake -> outreach execution -> signal detection -> routing -> booking -> handoff`
> The product should feel like a calm control tower, not a complicated workflow builder.

**NEW**:
> SignalLoop automates B2B outreach through two channels: multi-step email sequences and AI-powered cold calling. Marketing users set up campaigns and content. The system executes automatically — sending email followups on schedule, making voice calls using a reference script, detecting positive signals, and triggering appropriate followup actions.
> Phase 1: Email sequences + AI voice calling in English.
> Phase 2+: Additional languages, advanced analytics, CRM integration.

**Rationale**: The original promise described a human-operated platform. The actual need is automated execution with AI voice.

---

### 5.2 PRD Changes — New/Modified Functional Requirements

**REMOVE**: FR8 (template approval), FR9-FR13 (complex governance — keep only caps + quiet hours), FR21-FR23 (complex intent classification), FR26-FR27 (formal booking), FR28-FR30 (formal handoff packet), FR31-FR34 (KPI/audit dashboards — Phase 2)

**MODIFY**:
- FR6 → "The system must support email sequence templates with multiple steps and different content per step"
- FR14 → "The system must execute email sequences automatically based on configured step delays"
- FR19 → "The system must detect positive signals from email replies (reply content, reply timing)"
- FR20 → "The system must detect call outcomes from AI voice calls (answered, scheduling requested, objections raised, questions unanswered)"

**ADD**:
- FR-V1: The system must make automated outbound voice calls using an AI assistant
- FR-V2: The system must use a reference script file to guide the AI voice conversation
- FR-V3: The AI voice assistant must answer prospect questions using the script context
- FR-V4: For questions the AI cannot answer from the script, it must acknowledge the question and note it for team followup
- FR-V5: The AI voice assistant must ask the prospect if they want to schedule a call with a sales agent
- FR-V6: After each call, the system must email the team with a call summary including unanswered questions and scheduling requests
- FR-V7: The system must support ~50 cold calls per day with daily cap enforcement
- FR-V8: The AI voice assistant must operate in English (Phase 1), with multi-language support planned for future phases
- FR-S1: On positive/semi-positive email signal, the system must trigger two actions: schedule a followup call and send a demo links email
- FR-S2: On voice call with scheduling interest, the system must create or flag a scheduling request for the sales team

---

### 5.3 Architecture Changes

**REMOVE**:
- Section referencing MongoDB as event store → replace with PostgreSQL JSONB
- PyCasbin authorization → simple role middleware
- Formal approval workflow component
- Complex policy engine (keep daily cap + quiet hours check only)

**ADD new component — Voice AI Pipeline**:
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Call Queue   │────▶│ Twilio Voice  │────▶│ Media Stream│
│ (Redis)     │     │ (Outbound)   │     │ (WebSocket) │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │   STT       │
                                         │ (Real-time) │
                                         └──────┬──────┘
                                                │
                    ┌──────────────┐      ┌─────▼──────┐
                    │ Script/KB    │─────▶│   LLM      │
                    │ (PostgreSQL) │      │ (Groq 8B)  │
                    └──────────────┘      └─────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │   TTS       │
                                         │ (Streaming) │
                                         └──────┬──────┘
                                                │
                                         ┌──────▼──────┐
                                         │ Post-Call   │
                                         │ Automation  │
                                         └─────────────┘
```

**ADD new component — Sequence Engine**:
```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│ Sequence     │────▶│ Step Scheduler│────▶│ SendGrid     │
│ Definitions  │     │ (Worker/Cron) │     │ Adapter      │
│ (PostgreSQL) │     └───────┬───────┘     └──────┬───────┘
└──────────────┘             │                    │
                      ┌──────▼──────┐      ┌──────▼──────┐
                      │ Contact     │      │ Webhook     │
                      │ Sequence    │◀─────│ Handler     │
                      │ State       │      │ (Delivery/  │
                      │ (PostgreSQL)│      │  Reply)     │
                      └─────────────┘      └─────────────┘
```

---

### 5.4 UX Changes

**REMOVE screens**:
- Offer pack library
- Complex governance controls (keep simple caps + quiet hours section)
- Approval workflow screens
- Screens 5-2 through 5-6 (already identified as out-of-scope)

**MODIFY screens**:
- Template library → **Sequence builder** (define steps, content per step, delay between steps)
- Campaign setup → Add sequence assignment and script assignment

**ADD screens**:
- **Script management** — upload/edit voice scripts, preview Q&A sections
- **Call log** — list recent AI calls, outcome, recording playback, transcript, unanswered questions
- **Sequence monitor** — see contacts progressing through email steps, paused contacts, triggered followups
- **Operations dashboard** — emails sent/opened/replied, calls made/answered/scheduled, signals detected

---

### 5.5 Code Changes Summary

**Files to modify/remove**:

| File/Module | Action |
|---|---|
| `apps/api/app/infrastructure/db/mongodb/` | Remove entirely |
| `apps/api/app/infrastructure/authz/` (PyCasbin) | Remove entirely, replace with simple middleware |
| `apps/api/app/api/routes/approvals.py` | Remove |
| `apps/api/app/api/routes/offer_packs.py` | Remove or simplify significantly |
| `apps/api/app/domain/policies/approval_service.py` | Remove |
| `apps/api/app/domain/events/mongo_schema.py` | Remove (→ PostgreSQL JSONB) |
| `apps/api/app/domain/audit/mongo_audit.py` | Rewrite for PostgreSQL |
| `apps/web/src/features/templates/OfferPackLibraryPage.tsx` | Remove |
| `apps/web/src/components/Items/` | Remove (legacy CRUD) |
| `pyproject.toml` — `motor`, `casbin` dependencies | Remove |

**Files/modules to create**:

| Module | Purpose |
|---|---|
| `apps/api/app/domain/sequences/` | Sequence models, step scheduler, state machine |
| `apps/api/app/domain/voice/` | Voice AI pipeline, script loader, call orchestrator |
| `apps/api/app/infrastructure/providers/sendgrid.py` | SendGrid email adapter |
| `apps/api/app/infrastructure/providers/twilio_voice.py` | Twilio Voice adapter |
| `apps/api/app/infrastructure/providers/groq_llm.py` | Groq Llama 3.1 8B adapter for voice AI |
| `apps/api/app/infrastructure/providers/deepgram_stt.py` | Deepgram Nova-2 streaming STT adapter |
| `apps/api/app/infrastructure/providers/deepgram_tts.py` | Deepgram Aura streaming TTS adapter |
| `apps/api/app/api/routes/sequences.py` | Sequence CRUD + management API |
| `apps/api/app/api/routes/voice.py` | Script management, call log, Twilio webhooks |
| `apps/workers/worker_app/sequence_worker.py` | Email sequence step executor |
| `apps/workers/worker_app/call_worker.py` | Voice call scheduler + executor |
| `apps/workers/worker_app/postcall_worker.py` | Post-call email automation |
| `apps/web/src/features/sequences/` | Sequence builder UI |
| `apps/web/src/features/voice/` | Script management + call review UI |

---

## 6. Implementation Handoff

### Scope Classification: **Major**

This is a fundamental replan. The product's core value proposition has changed from "human-operated outreach management" to "automated email + AI voice execution."

### Handoff Plan

| Role | Responsibility |
|---|---|
| **Product Manager (John)** | Rewrite product brief and PRD with new FRs. Validate scope against user's stated needs. |
| **Architect (Winston)** | Update architecture doc — add voice AI pipeline, sequence engine. Remove MongoDB/PyCasbin sections. Define LLM integration pattern. |
| **UX Designer (Sally)** | Redesign screens — sequence builder, script management, call review, operations dashboard |
| **Scrum Master (Bob)** | Create new epic/story breakdown. Run sprint planning with new 4-epic structure. |
| **Developer (Amelia)** | Execute stories starting with Epic 1 (cleanup) then Epic 2 (email sequences) |

### Recommended Execution Order

1. **Rewrite planning artifacts first** (Brief → PRD → Architecture → Epics) — 1-2 days with agents
2. **Execute Epic 1** (cleanup/simplification) — 1 day
3. **Execute Epic 2** (email sequences) — 3-4 days. This is the easier channel and establishes execution patterns.
4. **Execute Epic 3** (AI voice pipeline) — 5-7 days. This is the harder piece. Can start in parallel with late Epic 2 work.
5. **Execute Epic 4** (signal actions + visibility) — 3-4 days. Ties both channels together.

### Success Criteria

Phase 1 is done when:

1. Marketing user can create an email sequence with 3+ steps and different content per step
2. Emails send automatically on schedule — step 1 on day 0, step 2 on day 3, step 3 on day 7 (configurable)
3. System detects email replies and pauses sequence for positive signals
4. On positive signal → system triggers followup call + sends demo links email
5. AI voice assistant makes cold calls following a reference script
6. Voice AI answers questions from the script, tables unknown questions for followup
7. Voice AI asks about scheduling with sales agent
8. After each call, team receives email summary with unanswered questions and scheduling requests
9. System respects daily caps (emails and 50 calls/day) and quiet hours
10. All of the above works in English

---

## 7. What This Proposal Removes (and Why)

| Removed Item | Why |
|---|---|
| MongoDB event store | PostgreSQL JSONB does the same thing without a 3rd datastore |
| PyCasbin RBAC | 2 admins don't need a policy engine. `if user.role != "admin"` is enough. |
| Formal approval workflow | Pilot doesn't need another admin to approve templates |
| Offer pack versioning/binding | Unnecessary abstraction layer over templates |
| Complex governance policy engine | Daily caps + quiet hours covers Phase 1. Full policy engine is Phase 2. |
| Signal classification (weak/medium/strong) | Simplified to positive/semi-positive/negative. Voice AI handles nuance live. |
| Formal booking workflow | Voice AI asks about scheduling directly. No calendar bridge needed for Phase 1. |
| Formal handoff packet | Post-call email to team replaces this |
| KPI dashboards | Phase 2. Operations dashboard covers Phase 1 visibility. |
| Ring promotion readiness | Phase 2 |
| Timeline/audit export | Phase 2 |

---

**End of Sprint Change Proposal**

*Awaiting product owner approval to proceed with artifact rewrites and implementation.*
