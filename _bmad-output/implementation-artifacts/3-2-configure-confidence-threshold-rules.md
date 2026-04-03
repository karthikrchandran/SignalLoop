# Story 3.2: Configure Confidence Threshold Rules

Status: backlog

## Story

As a Marketing Ops Admin,
I want configurable confidence thresholds that classify signals as weak, medium, or strong intent,
so that routing behavior precisely matches campaign strategy rather than using hardcoded rules.

## Acceptance Criteria

1. **Given** signal-routing settings are available for a workspace
   **When** I define threshold configuration (score ranges for weak/medium/strong)
   **Then** the configuration is persisted and active for new signals
   **And** the system validates non-overlapping ranges and correct min/max ordering.

2. **Given** a signal artifact is created (from 3.1)
   **When** confidence classification runs
   **Then** the signal's `confidence_tier` is set to `weak`, `medium`, or `strong` based on the active threshold profile
   **And** signals matching no tier (below weak threshold) are classified as `none` and do not trigger routing.

3. **Given** configuration is updated by an authorized operator
   **When** the new thresholds are saved
   **Then** the change is audit-logged with actor, timestamp, old values, and new values
   **And** only signals detected after the update use the new thresholds (existing signals are not reclassified retroactively).

4. **Given** no threshold profile is configured for a workspace
   **When** signal classification is attempted
   **Then** the system applies a safe default profile (weak: 30-59, medium: 60-79, strong: 80-100)
   **And** an operator warning is surfaced indicating custom thresholds have not been set.

## Tasks / Subtasks

- [ ] **Task 1 – Threshold configuration model and migration** (AC: 1, 4)
  - [ ] Add `confidence_threshold_profiles` table (workspace_id, profile_name, weak_min, medium_min, strong_min, is_active, created_by, updated_at)
  - [ ] Add Alembic migration chained after signal artifacts migration
  - [ ] Unique constraint: one active profile per workspace

- [ ] **Task 2 – Threshold configuration API** (AC: 1, 3)
  - [ ] `GET /workspaces/{wsId}/signal-thresholds` — return active profile
  - [ ] `POST /workspaces/{wsId}/signal-thresholds` — create or update profile
  - [ ] Validate range non-overlap and min < max ordering in request handler
  - [ ] On update: append audit entry with actor attribution and diff

- [ ] **Task 3 – Confidence classifier** (AC: 2, 4)
  - [ ] `apps/api/app/domain/signals/confidence_classifier.py`
  - [ ] Load active threshold profile for workspace (cache per workspace, invalidate on update)
  - [ ] Classify score → `weak` | `medium` | `strong` | `none`
  - [ ] Default profile fallback when no configured profile found

- [ ] **Task 4 – Wire classifier into signal detection pipeline** (AC: 2)
  - [ ] Call classifier after `SignalArtifact` creation (from 3.1 pipeline)
  - [ ] Update `confidence_tier` on artifact record

- [ ] **Task 5 – Tests** (AC: 1, 2, 3, 4)
  - [ ] Unit test: classifier correctly assigns tier from score for all boundaries
  - [ ] Unit test: overlapping range config is rejected
  - [ ] Unit test: default profile applied when workspace has no custom config
  - [ ] Integration test: threshold update audit log entry is created with diff

## Dev Notes

### Architecture Compliance

- Confidence scoring input for signal classification comes from the provider event normalization pipeline (e.g., sentiment score from transcription provider, keyword match count, response content length heuristics).
- Threshold profiles are workspace-scoped, not global. Support multi-workspace deployment from day one.
- Cache the active profile per workspace and invalidate on write (Redis or in-process with TTL). Do not query DB on every signal.
- Audit log for threshold changes must go to both PostgreSQL (governance_audit_events or similar) and MongoDB event envelope.

### Suggested File Touch Points

- `apps/api/app/domain/signals/confidence_classifier.py` (new)
- `apps/api/app/domain_models.py` (add ConfidenceThresholdProfile)
- `apps/api/app/api/routes/signal_thresholds.py` (new)
- `apps/api/app/alembic/versions/*_add_confidence_threshold_profiles.py` (new)
- `apps/api/tests/domain/test_confidence_classifier.py` (new)
- `apps/api/tests/api/routes/test_signal_thresholds.py` (new)

### References

- [Source: epics.md#Story-3.2-Configure-Confidence-Threshold-Rules]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#API-Communication-Patterns]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]

## Dev Agent Record

### Agent Model Used

_To be completed_

### Debug Log References

### Completion Notes List

### File List
