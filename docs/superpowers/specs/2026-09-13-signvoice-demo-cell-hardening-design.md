# Demo-Ready SignalVoice Customer Cell Hardening Design

Date: 2026-09-13
Status: approved for implementation

## Goal

Make SignalLoop voice execution demo-ready for isolated ARA Global and AI Consulting customer cells by ensuring outbound SignalVoice work can run only inside a deployment-owned workspace, with active consent, an active paid Voice Conversation agent deployment, provider credentials, usage evidence, and auditable denial paths.

## Scope

This phase covers the current Vercel and Supabase customer-cell direction. It does not introduce AWS infrastructure, pooled SaaS migration, OIDC, new CRM connectors, or live provider billing automation.

## Architecture

SignalLoop remains the voice execution owner. Each demo customer uses a separate SignalLoop runtime/database and binds to its matching eCRM cell through the existing installation projection boundary. Tenant identity is derived from persisted workspace binding and deployment configuration, never from browser input or a request-selected tenant.

Before a call worker invokes a voice provider, it must pass four gates:

1. The `CallRequest`, campaign, script, and contact belong to the same workspace.
2. The contact is actionable for `voice`; missing or ambiguous consent denies dispatch.
3. The workspace has exactly one active tenant/workspace binding and an active paid `VOICE_CONVERSATION` agent deployment.
4. The worker reserves daily voice-attempt capacity using the call request as the idempotency key.

If the provider accepts the call, capacity is finalized against the provider receipt. If validation fails before a provider call, the call is failed and no capacity is consumed. If provider outcome is ambiguous after a reservation, capacity remains held for reconciliation.

## Demo Cells

ARA Global and AI Consulting stay in separate SignalLoop deployments or runtime environments with separate databases. The checked-in env templates remain the source of demo identity:

- ARA Global: `workspace_ara_global`, `signalloop_ara_global`, `ara-global`
- AI Consulting: `workspace_ai_consulting`, `signalloop_ai_consulting`, `ai-consulting`

## Acceptance Criteria

- A queued voice call without an active `VOICE_CONVERSATION` deployment fails before provider resolution.
- A queued voice call with an active `VOICE_CONVERSATION` deployment reserves and finalizes capacity once when the provider returns a call SID.
- Same-key replay for a call request returns the existing usage ledger entry rather than double-counting capacity.
- Missing voice consent still denies before provider resolution.
- Workspace mismatch, paused workspace, daily cap, quiet hours, and provider errors keep their existing behavior.
- The runbook states the demo-cell smoke path for login, provider readiness, voice dispatch, post-call processing, eCRM delivery, and reconciliation.
