# Corrective Change Log Status — 2026-05-28

## Source

- `_bmad-output/planning-artifacts/corrective-story-set-2026-05-28.md`
- `_bmad-output/planning-artifacts/bob-correct-course-handoff-2026-05-28.md`

## Status Summary

All approved corrective stories are now implemented or closed through evidence review plus focused validation.

| Story | Title | Status | Closure Basis |
| --- | --- | --- | --- |
| `CC-1` | Wire Signal Detection to Trigger Execution | complete | Existing production wiring verified in code and supported by webhook + trigger tests. |
| `CC-2` | Build Provider and Operations Setup Console | complete | Existing settings/setup console verified in code and supported by setup/runtime tests. |
| `CC-3` | Replace Mock Sequence UI with Backend-Backed Management | complete | Implemented in this pass and validated with frontend build. |
| `CC-4` | Replace Demo Voice Setup UI with Backend-Backed Script and Campaign Setup | complete | Implemented in this pass and validated with frontend build. |
| `CC-5` | Align Governance Controls and Release-Readiness Validation | complete | Governance mismatch repaired, uniqueness enforced, readiness artifact published. |

## Story Notes

### CC-1

- Verified production path: SendGrid webhook creates signal event and invokes `process_signal(...)` in the same operating cycle.
- Focused evidence lives in:
  - `apps/api/app/api/routes/webhooks.py`
  - `apps/api/app/domain/signals/trigger_service.py`
  - `apps/api/tests/api/routes/test_webhooks.py`
  - `apps/api/tests/domain/test_trigger_service.py`

### CC-2

- No new implementation was required in this corrective pass.
- Existing operator setup home already covers provider status, callback URLs, worker readiness, and runtime configuration.
- Focused evidence lives in:
  - `apps/web/src/routes/_layout/settings.tsx`
  - `apps/api/app/api/routes/utils.py`
  - `apps/api/app/api/routes/workspace_runtime_config.py`

### CC-3

- Replaced the mock Sequences page with backend-backed reads and mutations.
- Added support for `PUT` and `DELETE` in the shared frontend request helper to support sequence CRUD.
- Focused evidence lives in:
  - `apps/web/src/features/sequences/SequencesPage.tsx`
  - `apps/web/src/lib/engagehub-api.ts`

### CC-4

- Replaced the demo Voice Agents page with a backend-backed script management and readiness surface.
- Operators can now inspect campaign-linked scripts, script preview sections, and live provider prerequisites from the product UI.
- Focused evidence lives in:
  - `apps/web/src/features/voice/VoiceAgentsPage.tsx`
  - `apps/api/tests/api/routes/test_scripts.py`

### CC-5

- Repaired the governance alignment slice in the code and closed the release-readiness documentation gap.
- Added workspace/campaign partial unique enforcement for `global_control_state` plus migration-time deduplication.
- Published release-readiness documentation in:
  - `_bmad-output/implementation-artifacts/corrective-release-readiness-2026-05-28.md`

## Validation Evidence

Validated directly in this corrective pass:

- `uv run pytest tests/api/routes/test_controls.py` → `15/15` passed
- `uv run alembic current` → `l7a8b9c0d1e2 (head)`
- `uv run pytest tests/infrastructure/providers/test_deepgram_stt.py tests/workers/test_sequence_worker.py tests/workers/test_call_worker.py` → `64/64` passed
- `npm run build` in `apps/web` → passed after `CC-3` and `CC-4`

## Authoritative Tracking Guidance

For the corrective increment, this file and `corrective-release-readiness-2026-05-28.md` should be treated as the authoritative closure record.

The original sprint tracker remains historically correct for the closed MVP sprint, but it does not represent the post-sprint corrective increment.