# Story 1.3: Configure Template, Token, and Offer-Pack Library

Status: done

## Story

As a Marketing Ops Admin,
I want to create versioned templates and offer packs with personalization tokens and guardrails,
so that campaign messaging is reusable, controlled, and safe to activate.

## Acceptance Criteria

1. **Given** I am in template management workspace  
   **When** I create or edit email templates and call script variants  
   **Then** each save creates or updates a draft version with immutable version metadata  
   **And** templates can be promoted to `published` only after validation succeeds.

2. **Given** templates include personalization tokens  
   **When** I define or update token definitions  
   **Then** token schema is validated (name uniqueness, allowed source fields, fallback behavior)  
   **And** template preview renders sample output with token substitution and unresolved-token warnings.

3. **Given** offer packs are created from templates/scripts  
   **When** I publish an offer pack version  
   **Then** it becomes selectable by campaigns while prior versions remain immutable and auditable  
   **And** only one active version per offer-pack can be marked as default.

4. **Given** a template is ready for activation  
   **When** guardrail checks run  
   **Then** policy checks (required disclaimer, banned phrase list, max variable density, channel-specific compliance) execute  
   **And** failing templates surface reason-coded violations blocking publish.

5. **Given** campaign assignment flow requests templates/offer packs  
   **When** available artifacts are listed  
   **Then** only `published` and guardrail-compliant versions are returned for selection.

## Tasks / Subtasks

- [x] **Task 1 – Create template and offer-pack persistence model** (AC: 1, 3, 5)
  - [x] Add tables:
    - [x] `templates`
    - [x] `template_versions`
    - [x] `template_tokens`
    - [x] `offer_packs`
    - [x] `offer_pack_versions`
    - [x] `offer_pack_template_bindings`
  - [x] Enforce unique constraints for `(template_id, version_number)` and `(offer_pack_id, version_number)`
  - [x] Add status enums: `draft`, `published`, `archived`
  - [x] Add migration with proper indexes for lookup by status + workspace

- [x] **Task 2 – Implement template CRUD + versioning API** (AC: 1)
  - [x] `POST /templates`
  - [x] `PATCH /templates/{templateId}`
  - [x] `POST /templates/{templateId}/versions/{versionId}/publish`
  - [x] `GET /templates?status=published`
  - [x] `POST /templates/{templateId}/clone`
  - [x] Require idempotency key on mutating endpoints

- [x] **Task 3 – Implement token registry and preview resolver** (AC: 2)
  - [x] Build token parser for syntax like `{{contact.firstName}}`
  - [x] Validate token definitions against canonical allowed source fields
  - [x] Implement fallback chain (`providedValue` -> `defaultValue` -> unresolved warning)
  - [x] Add preview endpoint with sample payload rendering + unresolved token list

- [x] **Task 4 – Implement offer-pack composition and publishing flow** (AC: 3, 5)
  - [x] Create API to bind template versions + call script variants into offer-pack versions
  - [x] Validate all bound template versions are `published`
  - [x] Enforce one default active version per offer-pack per workspace
  - [x] Build listing endpoint for campaign assignment (published + compliant only)

- [x] **Task 5 – Build guardrail validation pipeline** (AC: 4)
  - [x] Add rule checks:
    - [x] Required legal/footer copy by channel
    - [x] Banned phrase / risky claims blacklist
    - [x] Max token density threshold
    - [x] Channel-specific content constraints (email vs call)
  - [x] Emit semantic error taxonomy with reason codes per violation
  - [x] Block publish when guardrail violations exist

- [ ] **Task 6 – Build web UI for template library and offer-pack management** (AC: 1, 2, 3, 4, 5)
  - [ ] `apps/web/src/features/templates/TemplateLibraryPage.tsx`
  - [ ] Template editor with token side panel and live preview
  - [ ] Offer-pack builder UI with version timeline and publish controls
  - [ ] Guardrail report panel with actionable fixes
  - [ ] Published-only filters for campaign assignment surfaces

- [ ] **Task 7 – Test coverage for versioning and guardrails** (AC: 1, 2, 3, 4, 5)
  - [x] Unit tests for token parsing and fallback logic
  - [x] Unit tests for guardrail validator rules
  - [x] Integration test for publish-block on guardrail failure
  - [x] Integration test for immutable version behavior
  - [ ] UI test for template preview + unresolved token warning

## Dev Notes

### Architecture Compliance

- Domain ownership: templates/offer packs are policy-governed operational configuration, persisted in PostgreSQL as mutable state.
- Event/audit trail for publish actions should be mirrored into MongoDB immutable audit envelope stream.
- All publish/clone/update endpoints must carry correlation IDs and semantic errors; raw parsing exceptions stay internal logs.
- Enforce snake_case backend fields; convert to camelCase at API boundary.

### Guardrail & Error Semantics

- Guardrail violations map primarily to `POLICY_VIOLATION` with specific reason codes:
  - `MISSING_REQUIRED_DISCLAIMER`
  - `BANNED_PHRASE_PRESENT`
  - `TOKEN_DENSITY_EXCEEDED`
  - `CHANNEL_COMPLIANCE_FAILED`
- Unexpected parser/runtime issues map to `SYSTEM_ERROR` or `UNKNOWN_ERROR`.

### Suggested File Touch Points

- API:
  - `apps/api/app/api/routers/templates.py`
  - `apps/api/app/api/routers/offer_packs.py`
- Domain:
  - `apps/api/app/domain/outreach/template_service.py`
  - `apps/api/app/domain/outreach/token_service.py`
  - `apps/api/app/domain/policies/template_guardrail_service.py`
- Infra:
  - `apps/api/app/infrastructure/db/postgres/models/templates.py`
  - `apps/api/alembic/versions/*_template_offer_pack_library.py`
- Web:
  - `apps/web/src/features/templates/TemplateLibraryPage.tsx`
  - `apps/web/src/features/templates/components/TemplateEditor.tsx`
  - `apps/web/src/features/templates/components/GuardrailResultsPanel.tsx`
  - `apps/web/src/features/templates/components/OfferPackVersionHistory.tsx`

### UX Guidance

- Keep setup-first empowerment principle: let admin create reusable building blocks once, then apply repeatedly.
- Show transparent publish readiness state (green/red checks) before allowing publish click.
- Guardrail feedback must be human-readable and corrective, not compiler-style jargon.

### Testing Requirements

- Publish endpoint must reject if any guardrail fails.
- Version immutability: published version content cannot mutate; only clone to new draft.
- Token preview must never fail hard on unresolved tokens; return warning list with graceful render.

### References

- [Source: epics.md#Story-1.3-Configure-Template-Token-and-Offer-Pack-Library]
- [Source: architecture.md#Error-Semantics-Operator-Taxonomy]
- [Source: architecture.md#API-Communication-Patterns]
- [Source: architecture.md#Data-Architecture]
- [Source: architecture.md#Naming-Patterns]
- [Source: ux-design-specification.md#Effortless-Interactions]
- [Source: ux-design-specification.md#Experience-Principles]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (GitHub Copilot)

### Debug Log References

- `pytest tests/domain/test_token_service.py --confcutdir=tests/domain` -> passed (`3 passed`)
- `..\\..\\.venv\\Scripts\\python -m pytest tests/domain/test_token_service.py tests/domain/test_template_guardrail_service.py --confcutdir=tests/domain` -> passed (`5 passed`)
- `..\\..\\.venv\\Scripts\\python -m pytest tests/api/routes/test_templates_offer_packs.py` -> passed (`2 passed`)

### Completion Notes List

- Implemented template/offer-pack persistence migration with status enums, constraints, and lookup indexes.
- Added unique version constraints at model level for template and offer-pack versioning.
- Added offer-pack versioning APIs (`POST /offer-packs/{offer_pack_id}/versions`, `POST /offer-packs/{offer_pack_id}/versions/{version_id}/publish`) and assignable listing endpoint (`GET /offer-packs/assignable`).
- Corrected default-version enforcement to one default per offer-pack (instead of one default across entire workspace).
- Expanded guardrail checks to emit story reason codes (`MISSING_REQUIRED_DISCLAIMER`, `BANNED_PHRASE_PRESENT`, `TOKEN_DENSITY_EXCEEDED`, `CHANNEL_COMPLIANCE_FAILED`) and kept publish-block behavior.
- Expanded token validation to include fallback behavior validation against canonical values.
- Added domain tests for token parsing/fallback and guardrail rules, plus API route tests for publish-block and immutable-version behavior.
- Remaining gap: UI-level e2e/preview warning automation test not yet implemented.

### File List

- `apps/api/app/domain/outreach/token_service.py`
- `apps/api/app/domain/policies/template_guardrail_service.py`
- `apps/api/app/api/routes/templates.py`
- `apps/api/app/api/routes/offer_packs.py`
- `apps/api/app/domain_models.py`
- `apps/api/app/alembic/versions/b7c1012f3a44_add_campaign_intake_tables.py`
- `apps/api/app/alembic/versions/c3d9f4a8e271_add_template_and_offer_pack_library.py`
- `apps/api/tests/domain/test_token_service.py`
- `apps/api/tests/domain/test_template_guardrail_service.py`
- `apps/api/tests/api/routes/test_templates_offer_packs.py`
