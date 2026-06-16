# HTTP Mutation Idempotency Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend existing Redis-backed HTTP mutation idempotency to the SignalLoop template, script, and sequence mutation route families.

**Architecture:** Reuse `app.core.idempotency.run_idempotent_mutation()` rather than inventing a new helper. Route handlers keep their existing validation and transactional behavior inside small `*_once()` functions, while the public handlers pass stable operation names, workspace scope, route payloads, and the caller's `Idempotency-Key` into the shared idempotency runner.

**Tech Stack:** FastAPI, SQLModel, Redis idempotency helper, pytest, TestClient.

---

## File Structure

- Modify `apps/api/app/api/routes/templates.py`: wrap create, update, clone, and publish mutations with `run_idempotent_mutation()`.
- Modify `apps/api/app/api/routes/scripts.py`: wrap create, update, and delete mutations with `run_idempotent_mutation()` and require `Idempotency-Key` for update/delete.
- Modify `apps/api/app/api/routes/sequences.py`: wrap create, update, steps update, delete, and enroll mutations with `run_idempotent_mutation()` and require `Idempotency-Key` where missing.
- Modify `apps/api/tests/api/routes/test_templates_offer_packs.py`: add route-level replay and conflict coverage for templates.
- Modify `apps/api/tests/api/routes/test_scripts.py`: add route-level replay and conflict coverage for scripts.
- Modify `apps/api/tests/api/routes/test_sequences.py`: add route-level replay and conflict coverage for sequences.
- Modify `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`: record this P0 partial adoption status.

## Task 1: Template Mutation Idempotency

**Files:**
- Modify: `apps/api/app/api/routes/templates.py`
- Modify: `apps/api/tests/api/routes/test_templates_offer_packs.py`

- [x] **Step 1: Add RED route tests for template replay and conflict**

Add tests proving:

```python
def test_create_template_replays_same_idempotency_key(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    headers = _headers(superuser_token_headers, idempotency=True)
    body = {
        "name": "Replay template",
        "channel": "email",
        "subject": "Hello {{first_name}}",
        "content": "Hi {{first_name}}",
        "tokens": [
            {
                "name": "first_name",
                "source_field": "contact.first_name",
                "default_value": "there",
                "fallback_behavior": "default",
            }
        ],
    }

    first = client.post("/api/v1/templates/", headers=headers, json=body)
    second = client.post("/api/v1/templates/", headers=headers, json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    listed = client.get("/api/v1/templates/", headers=superuser_token_headers)
    matches = [row for row in listed.json()["data"] if row["name"] == "Replay template"]
    assert len(matches) == 1


def test_create_template_rejects_reused_idempotency_key_with_different_payload(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    headers = _headers(superuser_token_headers, idempotency=True)
    base = {
        "name": "Conflict template",
        "channel": "email",
        "subject": "One",
        "content": "One",
        "tokens": [],
    }

    first = client.post("/api/v1/templates/", headers=headers, json=base)
    second = client.post(
        "/api/v1/templates/",
        headers=headers,
        json={**base, "name": "Conflict template changed"},
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
```

- [x] **Step 2: Run the template tests and verify RED**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_templates_offer_packs.py::test_create_template_replays_same_idempotency_key tests/api/routes/test_templates_offer_packs.py::test_create_template_rejects_reused_idempotency_key_with_different_payload -q
```

Expected: replay test fails because the second request creates a duplicate row, or conflict test fails because the reused key is not rejected.

- [x] **Step 3: Wrap template mutations with `run_idempotent_mutation()`**

In `templates.py`, import `Request` and `run_idempotent_mutation()`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.idempotency import run_idempotent_mutation
```

Update each mutating public handler to accept `request: Request` and `idempotency_key: IdempotencyKeyDep`, then return:

```python
return await run_idempotent_mutation(
    request,
    idempotency_key=idempotency_key,
    workspace_id=workspace_id,
    operation="templates.create",
    request_payload=body.model_dump(mode="json"),
    mutation=lambda: _create_template_once(
        session=session,
        current_user=current_user,
        workspace_id=workspace_id,
        body=body,
    ),
)
```

Extract the existing body into `_create_template_once()`. Use operation names:

```text
templates.create
templates.update
templates.clone
templates.publish
```

For routes without a body, use payloads such as:

```python
request_payload={"template_id": str(template_id)}
request_payload={"template_id": str(template_id), "version_id": str(version_id)}
```

- [x] **Step 4: Run template route tests and verify GREEN**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_templates_offer_packs.py -q
```

Expected: selected template tests pass.

## Task 2: Script Mutation Idempotency

**Files:**
- Modify: `apps/api/app/api/routes/scripts.py`
- Modify: `apps/api/tests/api/routes/test_scripts.py`

- [x] **Step 1: Add RED route tests for script replay and conflict**

Add tests proving create replay and payload conflict. Use existing campaign fixtures/helpers in `test_scripts.py`; create a script with the same `Idempotency-Key` twice and assert only one active script row is listed.

- [x] **Step 2: Run the new script tests and verify RED**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_scripts.py::test_create_script_replays_same_idempotency_key tests/api/routes/test_scripts.py::test_create_script_rejects_reused_idempotency_key_with_different_payload -q
```

Expected: replay or conflict behavior fails before implementation.

- [x] **Step 3: Wrap script mutations**

In `scripts.py`, import `Request` and `run_idempotent_mutation()`.

Require `idempotency_key: IdempotencyKeyDep` for update and delete as well as create. Wrap these operations:

```text
scripts.create
scripts.update
scripts.delete
```

Use `body.model_dump(mode="json")` for create/update and `{"script_id": str(script_id)}` for delete.

- [x] **Step 4: Run script route tests and verify GREEN**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_scripts.py -q
```

Expected: selected script tests pass.

## Task 3: Sequence Mutation Idempotency

**Files:**
- Modify: `apps/api/app/api/routes/sequences.py`
- Modify: `apps/api/tests/api/routes/test_sequences.py`

- [x] **Step 1: Add RED route tests for sequence replay and conflict**

Add tests proving create replay and payload conflict. Use existing campaign helpers in `test_sequences.py`; create a sequence with the same `Idempotency-Key` twice and assert only one sequence row is listed.

- [x] **Step 2: Run the new sequence tests and verify RED**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_sequences.py::test_create_sequence_replays_same_idempotency_key tests/api/routes/test_sequences.py::test_create_sequence_rejects_reused_idempotency_key_with_different_payload -q
```

Expected: replay or conflict behavior fails before implementation.

- [x] **Step 3: Wrap sequence mutations**

In `sequences.py`, import `Request` and `run_idempotent_mutation()`.

Require `idempotency_key: IdempotencyKeyDep` for update, steps update, delete, and enroll as well as create. Wrap these operations:

```text
sequences.create
sequences.update
sequences.steps.update
sequences.delete
sequences.enroll
```

Use route ids and `body.model_dump(mode="json")` in `request_payload` so the same key with a different body or different target route returns `409`.

- [x] **Step 4: Run sequence route tests and verify GREEN**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/api/routes/test_sequences.py -q
```

Expected: selected sequence tests pass.

## Task 4: Verification And Status Note

**Files:**
- Modify: `_bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md`

- [x] **Step 1: Run focused idempotency and route gates**

Run:

```powershell
cd apps\api
$env:PROJECT_NAME='SignalLoop'; $env:POSTGRES_SERVER='localhost'; $env:POSTGRES_USER='postgres'; $env:FIRST_SUPERUSER='admin@example.com'; $env:FIRST_SUPERUSER_PASSWORD='local-dev-password'; uv run pytest tests/unit/test_idempotency.py tests/api/routes/test_templates_offer_packs.py tests/api/routes/test_scripts.py tests/api/routes/test_sequences.py tests/api/routes/test_controls.py tests/unit/test_call_manual_actions.py -q
```

Expected: all selected tests pass.

- [x] **Step 2: Update BMAD status**

Under `### P0: Implement Real HTTP Mutation Idempotency`, add:

```markdown
Status update 2026-06-15: This pass reused the existing Redis-backed `run_idempotent_mutation()` helper across the template, script, and sequence mutation route families. These routes now replay same-key/same-payload responses, reject same-key/different-payload requests with `409`, and require `Idempotency-Key` on update/delete/enroll mutations in the selected route families. Remaining adoption still needs a sweep across campaign import/audience/strategy/segment, provider credential, runtime config, and dead-letter mutations.
```

- [x] **Step 3: Run diff checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only intended files changed.

- [x] **Step 4: Commit the slice**

Run:

```powershell
git add apps/api/app/api/routes/templates.py apps/api/app/api/routes/scripts.py apps/api/app/api/routes/sequences.py apps/api/tests/api/routes/test_templates_offer_packs.py apps/api/tests/api/routes/test_scripts.py apps/api/tests/api/routes/test_sequences.py _bmad-output/implementation-artifacts/signalloop-phase1-open-review-fix-plan-2026-06-07.md docs/superpowers/plans/2026-06-15-http-mutation-idempotency-adoption.md
git commit -m "feat: adopt mutation idempotency for content routes"
```

## Spec Coverage Review

- Duplicate POST/PATCH/DELETE with same key and same body returns original result: covered for create routes in each route family and implemented through shared helper for the remaining selected mutations.
- Same key with different body returns `409 Conflict`: covered for create routes in each route family and implemented through shared helper for the remaining selected mutations.
- Concurrent duplicate submissions do not execute twice: inherited from existing `run_idempotent_mutation()` unit tests.
- Redis unavailable behavior: inherited from existing `run_idempotent_mutation()` unit tests, which currently fail open for local/demo operation.
- Initial endpoint coverage: partial adoption for template, script, and sequence mutations; the BMAD note records remaining route families explicitly.
