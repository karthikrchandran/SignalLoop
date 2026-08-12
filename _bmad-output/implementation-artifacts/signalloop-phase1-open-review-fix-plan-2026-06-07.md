# SignalLoop Phase 1 Open Review Fix Plan

Date: 2026-06-07

Type: Explanation and implementation plan

Audience: Project owner and developers preparing the remaining SignalLoop Phase 1 hardening work

Scope: This document summarizes the open items from the SignalLoop Phase 1 code review after the first fix pass, and reconciles the provider inventory with the later near-zero demo stack / open-source provider work.

## Current Status After First Fix Pass

The first fix pass closed several high-risk SignalLoop Phase 1 findings:

- Launched sequence and post-call workers now enforce global pause, campaign pause, and campaign caps before provider side effects.
- Worker provider calls now persist outbound intent before calling SendGrid or Twilio, with in-flight protection to reduce duplicate sends on retries.
- SendGrid webhook handling now fails closed when signatures are missing or invalid.
- SendGrid webhook replay/dedupe now uses persisted provider event records.
- Provider credential `config_json` now rejects or redacts secret-like keys instead of returning raw sensitive configuration.
- Focused worker/provider tests were added and passed in the local environment.

The remaining work is not a repeat of those fixed items. The backlog below is focused on places where the same design principles still need to be applied across the broader SignalLoop surface.

## Provider Inventory Correction

The earlier review language called out SendGrid, Twilio, Deepgram, and Groq because those are the historical/default SignalLoop providers and they are still hard-coded in parts of setup/readiness UX. That wording was incomplete if read as the full current provider inventory.

There are three different levels of provider support in the codebase:

1. Historical/default providers

   These are the original production-oriented defaults used by the SignalLoop setup overview and default credential resolver:

   - Email: SendGrid
   - Voice/SMS: Twilio
   - STT/TTS: Deepgram
   - LLM: Groq

2. Implemented registry/catalog providers

   The provider registry now includes several additional adapters/options beyond the historical defaults:

   - Email: SendGrid, SMTP
   - Voice: Twilio Voice
   - STT: Deepgram, Faster Whisper Local
   - TTS: Deepgram
   - LLM: Groq, OpenAI, OpenRouter, Together, Ollama Local

   This is where the near-zero demo stack work shows up: SMTP for local/free email, Ollama Local for local LLM, and Faster Whisper Local for local/batch STT.

3. Enum/planned providers

   The domain enum and provider-selection migration contain additional provider identifiers that are not all fully adapter-backed yet:

   - Email: SES, Postmark, Mailgun, Brevo, Resend
   - STT: Whisper API
   - TTS: Aura, ElevenLabs, PlayHT, Polly, Piper Local, Coqui Local
   - LLM: Anthropic, Gemini
   - Chatbot/channel providers: Facebook, WhatsApp, Telegram, LinkedIn redirect variants

   These should be treated as planned or schema-level values unless the registry has a factory, the catalog exposes the option, credentials/runtime config are resolved, and tests prove the provider works end to end.

### Why The Confusion Happened

The near-zero demo stack added provider abstraction and local/open-source options, but some SignalLoop readiness and settings screens still reflect the older provider set.

Important examples:

- `apps/api/app/api/routes/utils.py` returns setup overview integrations for SendGrid, Twilio Voice, Deepgram, Groq, and team notifications.
- The same setup overview still evaluates worker readiness against fixed provider names instead of the active workspace provider selections.
- `apps/web/src/routes/_layout/settings.tsx` still presents credential/runtime fields oriented around SendGrid, Twilio, Deepgram, Groq, and team notifications.
- `apps/api/app/infrastructure/providers/registry.py` exposes more provider options than the setup overview currently acknowledges.

So the accurate review statement is:

> SignalLoop still has historical/default-provider assumptions in setup/readiness UX and some direct provider-call paths, even though the provider registry now includes additional open-source/local and multi-vendor options.

## Open Review Backlog

### P0: Finish Provider Side-Effect Safety Outside The Fixed Workers

Status update 2026-06-15: This slice hardened the remaining automatic email
and call side-effect paths found during the P0 audit. Signal trigger emails and
API post-call summary emails and the scheduled `signalloop-workers`
post-call path now persist an `OutboxEvent` intent before the provider call,
pass the same stable key as adapter idempotency metadata, and skip only
published duplicate sends on retry. Unpublished intents are treated as
unknown/in-progress provider outcomes and rejected provider responses leave the
intent unpublished. Both API-app workers and scheduled `signalloop-workers`
sequence/call workers also no longer auto-resend `pending` sends or auto-redial
`initiating` calls where the provider outcome is unknown.

At the start of this review item, the originally fixed worker paths were not
the whole risk surface. The broader codebase still needed an audit for direct
provider side effects that bypassed the newer provider-selection and
durable-intent pattern.

Known paths to inspect and fix:

- `apps/api/app/domain/signals/trigger_service.py`
- `apps/api/app/api/routes/calls.py`
- `apps/api/app/workers/postcall_worker.py`

Expected problems:

- Direct `SendGridAdapter` construction or SendGrid-specific assumptions.
- Provider calls that may happen before a durable send/call intent has been committed.
- Calls that do not consistently resolve the active workspace provider.
- Weak dedupe keys for retryable side effects.

Fix approach:

- Route outbound email, call, and notification sends through a shared provider-aware service.
- Persist a durable intent before the external provider call.
- Commit the intent before making the provider call.
- Record provider response status after the call.
- Use workspace provider selection instead of hard-coded SendGrid where a capability-based adapter exists.
- Add stable dedupe keys such as `signal:{signal_id}:action:{action_type}` or `call_request:{request_id}:demo_email`.

Acceptance criteria:

- No SignalLoop business/domain route path directly constructs provider-specific adapters when a capability resolver exists.
- Retrying a signal action or call request does not duplicate provider sends.
- Tests cover retry behavior and active provider selection.

### P0: Implement Real HTTP Mutation Idempotency

Status update 2026-06-15: This pass reused the existing Redis-backed
`run_idempotent_mutation()` helper across the template, script, and sequence
mutation route families. These routes now replay same-key/same-payload
responses, reject same-key/different-payload requests with `409`, and require
`Idempotency-Key` on update/delete/enroll mutations in the selected route
families. Remaining adoption still needs a sweep across campaign
import/audience/strategy/segment, provider credential, runtime config, and
dead-letter mutations.

The API has an `IdempotencyKeyDep` dependency that requires the `Idempotency-Key` header, and there are helper functions in `apps/api/app/core/idempotency.py`. The review gap is that this does not yet provide full request/response idempotency for generic mutations.

Current risk:

- A client retry can repeat a non-worker mutation even when it supplies the same idempotency key.
- The frontend helper can generate a fresh key per request instead of preserving the key across retries for the same user action.
- Same key with different payload may not be rejected consistently.

Fix approach:

- Add reusable mutation idempotency handling backed by Redis.
- Namespace keys by workspace, HTTP method, route, and idempotency key.
- Store a hash of the request body.
- Return the original response for same key and same request hash.
- Return `409 Conflict` for same key and different request hash.
- Use an in-progress lock with TTL to prevent concurrent duplicate execution.
- Decide explicitly whether Redis outage should fail closed or return `503` for release-critical mutations.
- Update frontend mutation helpers so a retry reuses the same idempotency key for the same user action.

Initial endpoint coverage:

- SignalLoop control mutations
- Campaign create/update/import/audience/strategy/segment mutations
- Template/script/sequence mutations
- Provider credential mutations
- Runtime config mutations
- Dead-letter retry/dismiss mutations if present

Acceptance criteria:

- Duplicate POST/PATCH/DELETE with the same idempotency key and same body returns the original result.
- Same idempotency key with a different body returns `409 Conflict`.
- Concurrent duplicate submissions do not execute the mutation twice.
- Tests cover success replay, payload conflict, concurrent in-progress behavior, and Redis unavailable behavior.

### P1: Enforce Workspace Authorization / BOLA Protection

Several SignalLoop routes depend on `X-Workspace-Id` plus an admin role. That is not enough if users can belong to different workspaces, because a caller could potentially switch the header to access another workspace.

Fix approach:

- Add or confirm a workspace membership model.
- Replace raw `require_workspace_id` usage with a workspace context dependency that validates the current user belongs to the requested workspace.
- Allow cross-workspace access only for explicit super-admin/system roles.
- Seed default workspace membership for local/demo users.
- Keep background/service workers using trusted internal workspace IDs, not request headers.

Acceptance criteria:

- Admin user from workspace A cannot access or mutate workspace B by changing `X-Workspace-Id`.
- Super-admin behavior is explicit and tested.
- All SignalLoop route dependencies use the validated workspace context.
- Tests cover read, write, and provider credential access across workspaces.

If the intended product model is single-tenant only, the alternative is to document that explicitly and remove or lock down user-controlled workspace switching.

### P1: Align Setup/Readiness UX With Provider Selection

Status update 2026-06-15: Backend setup overview was already capability-aware
at the start of this slice. This pass completed the frontend Provider Setup
alignment by rendering setup-overview integrations, worker readiness, callback
host status, and readiness errors from `/api/v1/utils/setup-overview/`, while
keeping provider selection on the catalog-backed `/settings/providers` route.

This is the direct fix for the provider confusion.

Current state:

- Backend setup overview still returns a fixed list centered on SendGrid, Twilio Voice, Deepgram, and Groq.
- Frontend settings still present historical provider cards and runtime fields.
- Provider registry and provider-selection models support more options than the setup overview shows.
- Twilio SMS is visible in the provider catalog, but the registry factory map currently does not show a matching SMS adapter factory.

Fix approach:

- Make setup overview capability-aware rather than provider-name-aware.
- Use provider catalog, workspace provider selections, and credential/runtime resolvers to report readiness.
- Report the active provider for each capability:
  - email
  - voice
  - sms, if fully implemented
  - stt
  - tts
  - llm
- Update the frontend to consume provider options and provider selections instead of rendering only historical fixed cards.
- Decide whether Twilio SMS is fully supported:
  - If yes, add the missing registry factory and tests.
  - If no, hide SMS from the catalog until it is backed by an adapter.
- Decide which enum-only providers should become real providers in Phase 1 versus future backlog.

Acceptance criteria:

- SMTP, Ollama Local, and Faster Whisper Local appear as real selectable/configurable options where supported.
- Setup readiness reflects the active selected provider, not just the historical default provider.
- Provider catalog contains only options that can actually be resolved and used.
- Local demo setup does not incorrectly ask for paid vendor keys for capabilities configured to use local/free providers.

### P1: Extend Webhook Replay Dedupe Beyond SendGrid

SendGrid webhook replay protection was fixed in the first pass. Twilio callback handling should receive the same review treatment.

Current risk:

- Twilio callbacks can be retried by the provider.
- Status callbacks and recording callbacks may repeat or arrive out of order.
- The route verifies Twilio signatures and applies status transitions, but provider event replay dedupe should be explicit and persisted.

Fix approach:

- Use `ProviderEventLog` for Twilio status and recording callbacks.
- Derive a stable provider event ID from Twilio payload fields such as `CallSid`, callback type, status, timestamp, and recording SID where available.
- Skip already-processed callback events.
- Preserve monotonic call-status transitions.

Acceptance criteria:

- Replayed Twilio callback does not duplicate state transitions or side effects.
- Out-of-order statuses do not regress terminal call state.
- Tests cover duplicate callbacks and out-of-order callback sequences.

### P2: Clean Up Generated Client Discipline

The project context says normal frontend API calls should use the generated client. SignalLoop frontend code still uses raw wrapper calls in several areas.

Fix approach:

- Audit SignalLoop frontend API calls.
- Confirm all backend endpoints are represented in OpenAPI.
- Update OpenAPI where endpoint contracts are missing or stale.
- Regenerate the frontend client.
- Replace ordinary JSON request calls with generated client methods.
- Keep explicit exceptions only for SSE, streaming exports, file downloads, or cases where generated-client support is not practical.

Acceptance criteria:

- SignalLoop normal JSON calls use generated client methods.
- Raw wrapper exceptions are documented and limited.
- OpenAPI remains aligned with route behavior.

### P2: Remove The Route-Test Pgvector Blocker Without Docker

Status: resolved for the shared route-test suite on 2026-08-12. The root test
fixture attempts to enable pgvector and otherwise excludes vector-backed tables;
route modules must not bypass it with an unfiltered `SQLModel.metadata.create_all`.
`tests/unit/test_route_database_portability.py` enforces that guard.

The original local route-test blocker was not Docker itself; it was that the test database attempted to create chatbot vector columns without pgvector installed.

Observed issue:

- Chatbot models include `embedding vector(768)`.
- Test setup using `SQLModel.metadata.create_all(...)` reaches that type before the `vector` extension is available.
- On a machine without Docker/native pgvector, SignalLoop route tests can fail before reaching the routes under test.

Options without Docker:

- Install pgvector into the native local PostgreSQL instance and run `CREATE EXTENSION IF NOT EXISTS vector;`.
- Change test setup so migrations create the extension before vector columns are created.
- Avoid global metadata creation for route slices that do not need chatbot vector models.
- Split SignalLoop route tests from chatbot vector-model setup where practical.

Acceptance criteria:

- SignalLoop route tests can run locally without Docker.
- If native pgvector is required, setup instructions are explicit.
- Route tests for provider credentials, webhooks, controls, and idempotency are no longer blocked by unrelated chatbot vector schema setup.

### P3: Reduce Async Route Blocking From Sync DB Sessions

Several async route functions use synchronous SQLModel sessions. This is lower priority than correctness/security issues, but it can block the event loop under load.

Fix options:

- Convert routes that do not await anything into normal sync route handlers.
- Move blocking DB/provider work into threadpool boundaries.
- Plan a broader AsyncSession migration if the app needs high concurrency on these surfaces.

Acceptance criteria:

- High-traffic async routes do not perform long synchronous DB/provider work directly on the event loop.
- Any migration preserves existing transactional behavior.

## Provider Support Decision Matrix

| Capability | Implemented now | Default today | Local/open-source option | Main gaps |
| --- | --- | --- | --- | --- |
| Email | SendGrid, SMTP | SendGrid | SMTP with local catcher/mailpit-style tooling | Setup UX still centers SendGrid; some direct SendGrid call paths need provider resolver |
| Voice | Twilio Voice | Twilio | None for PSTN/Media Streams in current stack | Twilio remains required for production PSTN voice unless a SIP/WebRTC/local voice carrier architecture is added |
| SMS | Catalog shows Twilio SMS | Twilio | None in current stack | Registry factory gap needs implement-or-hide decision |
| STT | Deepgram, Faster Whisper Local | Deepgram | Faster Whisper Local | Faster Whisper is suitable for local/batch transcription, not a drop-in real-time media-stream replacement |
| TTS | Deepgram | Deepgram | Enum includes local TTS names | Piper/Coqui/etc. are schema/planned until adapters, runtime config, and tests exist |
| LLM | Groq, OpenAI, OpenRouter, Together, Ollama Local | Groq | Ollama Local | Setup overview still centers Groq instead of active workspace selection |
| Chatbot channels | Separate chatbot channel provider registry | N/A for SignalLoop Phase 1 outbound readiness | Some redirect/local dev flows | Keep separate from SignalLoop email/voice/SMS provider readiness unless a shared provider contract is intentionally introduced |

## Suggested Fix Order

1. Provider readiness/setup UX alignment

   This should come first because it resolves the immediate confusion and prevents the UI from asking for paid provider keys when local/open-source providers are selected.

2. Remaining provider side-effect safety

   Finish the durable-intent/provider-selection pattern outside the already-fixed workers.

3. HTTP mutation idempotency

   Protect admin/user-triggered mutations from duplicate browser retries and network retries.

4. Workspace authorization

   Close the BOLA class of bugs before broader release.

5. Twilio webhook replay dedupe

   Apply the same provider-event replay discipline now used for SendGrid.

6. Generated client cleanup

   Bring frontend API consumption back in line with project rules.

7. Route-test pgvector unblock

   Make route tests runnable locally without requiring Docker. If native pgvector is the chosen path, document the native setup steps clearly.

## Release Readiness Checklist

- Active provider selections are shown in setup/readiness UI.
- SMTP, Ollama Local, and Faster Whisper Local are selectable/configurable where supported.
- Setup readiness does not require SendGrid/Groq/Deepgram keys when the active provider for that capability is local or SMTP.
- Provider catalog contains only adapter-backed providers, or unsupported enum-only providers are clearly hidden.
- Direct SendGrid/Twilio calls outside infrastructure/provider services are removed or justified.
- Provider side effects persist durable intent before external calls.
- Generic mutating routes enforce idempotency replay/conflict behavior.
- Workspace access validates membership, not just the caller-supplied workspace header.
- SendGrid and Twilio webhook replay behavior is persisted and tested.
- SignalLoop route tests run locally without Docker, or native pgvector setup is documented and verified.
- Worker/provider tests remain green after the broader changes.
