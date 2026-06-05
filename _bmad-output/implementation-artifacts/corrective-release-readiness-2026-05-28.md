# Corrective Release Readiness — 2026-05-28

## Purpose

This report closes `CC-5` from the approved corrective story set by documenting what is now implemented, what was validated in this corrective pass, and which runtime conditions still determine whether the deployment is genuinely operable end to end.

Primary planning source:

- `_bmad-output/planning-artifacts/corrective-story-set-2026-05-28.md`

## Executive Summary

Corrective implementation is complete for the approved `CC-1` through `CC-5` slice.

The current honest release posture is:

- buildable
- migration-aligned
- focused-slice validated
- still dependent on environment readiness for live provider-backed operation

This is no longer blocked by the previously stale governance controls path or the previously ambiguous controls uniqueness behavior.

## Implemented Capability

### CC-1 Signal Automation Wiring

- Positive email reply handling is wired into trigger execution through the production webhook flow.
- Trigger execution continues to queue follow-up actions through the existing signal domain.

Primary code evidence:

- `apps/api/app/api/routes/webhooks.py`
- `apps/api/app/domain/signals/trigger_service.py`
- `apps/api/tests/api/routes/test_webhooks.py`
- `apps/api/tests/domain/test_trigger_service.py`

### CC-2 Provider And Operations Setup Console

- Provider/runtime setup and readiness surfaces already existed and remain the authoritative operator setup home.
- Callback URLs, integration status, worker readiness, provider credentials, and runtime configuration are exposed through the live backend-backed settings flows.

Primary code evidence:

- `apps/web/src/routes/_layout/settings.tsx`
- `apps/api/app/api/routes/utils.py`
- `apps/api/app/api/routes/workspace_runtime_config.py`
- `apps/api/tests/api/routes/test_utils.py`
- `apps/api/tests/api/routes/test_workspace_runtime_config.py`

### CC-3 Sequence UI Integration

- The Sequences page now reads live backend sequence data.
- Create, edit, step upsert, delete, and enroll flows now use the real API.
- Preview content and personalization tokens now reflect backend-backed sequence content rather than mock state.

Primary code evidence:

- `apps/web/src/features/sequences/SequencesPage.tsx`
- `apps/web/src/lib/engagehub-api.ts`

### CC-4 Voice Setup Integration

- The Voice Agents demo surface has been replaced with a backend-backed script management view.
- Script CRUD now uses live backend endpoints.
- Campaign-linked scripts, parsed preview content, and provider readiness are surfaced in-product.
- The page explicitly calls out callback-host prerequisites so operators do not mistake saved config for live readiness.

Primary code evidence:

- `apps/web/src/features/voice/VoiceAgentsPage.tsx`
- `apps/api/app/api/routes/scripts.py`
- `apps/api/tests/api/routes/test_scripts.py`

### CC-5 Governance And Release Alignment

- Governance controls no longer depend on the stale `/api/v1/policies/` route for the repaired slice under review.
- `global_control_state` uniqueness is enforced correctly for nullable campaign scope through partial unique indexes plus migration-time deduplication.
- This release-readiness artifact now records the distinction between implemented capability and environmental prerequisites.

Primary code evidence:

- `apps/api/app/domain_models.py`
- `apps/api/app/alembic/versions/l7a8b9c0d1e2_enforce_unique_global_control_state_scope.py`
- `apps/api/tests/api/routes/test_controls.py`

## Focused Validation Run In This Corrective Pass

Executed during this pass:

- `uv run pytest tests/api/routes/test_controls.py`
  - Result: passed `15/15`
- `uv run alembic current`
  - Result: `l7a8b9c0d1e2 (head)`
- `uv run pytest tests/infrastructure/providers/test_deepgram_stt.py tests/workers/test_sequence_worker.py tests/workers/test_call_worker.py`
  - Result: passed `64/64`
- `npm run build` from `apps/web`
  - Result: passed after the `CC-3` and `CC-4` frontend integrations

Repository-backed automated coverage also exists for the repaired areas:

- webhook signal invocation: `apps/api/tests/api/routes/test_webhooks.py`
- trigger execution behavior: `apps/api/tests/domain/test_trigger_service.py`
- setup overview and callback reporting: `apps/api/tests/api/routes/test_utils.py`
- script CRUD and preview: `apps/api/tests/api/routes/test_scripts.py`

## Environmental Prerequisites

Release-readiness still depends on the following runtime conditions:

1. Postgres and Redis must be running and reachable.
2. Provider credentials or runtime config must be present for SendGrid, Twilio, Deepgram, and Groq where those flows are used.
3. Worker processes must be running for sequence execution, call execution, and post-call processing.
4. The configured callback host must be public, not local-only, for Twilio webhook and media-stream operation.
5. Workspace-level runtime config must be populated where the deployment relies on workspace-scoped secrets instead of environment-only settings.

## Known Operational Caveats

1. This pass validates the repaired slices with focused tests and build checks, not with one monolithic end-to-end environment test run.
2. Live voice execution still depends on public callback reachability and valid telephony/AI provider credentials.
3. The frontend production build still emits Vite chunk-size warnings; this is not a correctness blocker, but it remains a delivery-quality follow-up.

## Release Decision

For the corrective increment itself, status is:

- `CC-1` complete
- `CC-2` complete
- `CC-3` complete
- `CC-4` complete
- `CC-5` complete

For live release promotion, status is:

- technically ready once environment prerequisites are satisfied
- honest caveat: operator success still depends on public callback configuration and active provider/runtime setup