# Admin E2E Contract Stabilization Design

**Date:** 2026-08-12
**Status:** approved for implementation

## Problem

The Playwright suite still asserts the retired welcome dashboard after login, while the root route now renders Revenue OS. Its admin coverage also runs against a shared API port and in parallel, which makes user-creation flows hard to observe and vulnerable to cross-test interference.

## Decision

Retain the current product behavior and stabilize test infrastructure:

- Login helpers and login tests assert the actual Revenue OS landing screen after a successful login.
- Admin tests keep the superuser user-management contract at /admin, but assert tenant-admin framing plus the Users section instead of treating the retired dashboard as the post-login contract.
- Introduce a dedicated Playwright API base URL and serial execution for stateful admin-user CRUD tests. The runner must use an explicitly supplied local API URL; it must not silently share the service on port 8001.
- Capture API-backed mutations in the test by waiting for their actual response, so an HTTP failure is reported with its status rather than surfacing only as a missing toast.

## Out of scope

No changes to product authorization, tenant capability semantics, API endpoints, CORS policy, schemas, providers, or Sales Agent behavior.

## Acceptance criteria

1. Successful login tests assert Revenue OS.
2. Admin CRUD tests reliably await API mutation responses and report a response failure directly.
3. A serial, isolated API-backed admin run passes against an explicitly supplied temporary API URL.
4. The existing mocked dashboard/contact browser tests and frontend build remain green.
