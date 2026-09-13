# eCRM installation projections

This is the SignalLoop/RevenueOS installation binding and projection operations runbook. All examples require an authenticated workspace context; a body, query, or ordinary header cannot choose another workspace or eCRM cell. Synthetic acceptance uses only `.synthetic.invalid` identities and injected local transports, with no provider calls.

SignalLoop binds each authenticated workspace to one eCRM cell through
`ecrm_installation_binding`. The binding is server-owned: request bodies, query
parameters, and worker arguments cannot replace the authenticated workspace or
the stored cell URL, cell identity, or credential reference.

## Configuration

Provision `ECRM_INSTALLATION_ENDPOINTS` and
`ECRM_INSTALLATION_SECRET_REFERENCES` in deployment configuration. Each public
secret-reference ID maps to one allowlisted environment variable and one eCRM
cell; callers can never submit an environment-variable name. The built-in
resolver fails closed when either the reference or its value is absent. Store
only the reference, never the credential value. Production secret-manager
adapters implement `SecretResolver` and are injected at deployment time. OIDC
and external CRM connectors remain intentionally inactive.

Apply the database migration before enabling delivery:

```powershell
cd apps/api
uv run alembic upgrade head
```

Create a binding through `PUT /api/v1/ecrm-installations/binding` while
authenticated as a workspace admin and sending `X-Workspace-Id`. The response
deliberately omits `credential_secret_ref` and all secret values.


## Demo customer configuration

For the ARA Global and AI Consulting demos, run two separate SignalLoop deployments or runtime environments. Do not point both workspaces at the same SignalLoop database.

| Demo cell | SignalLoop env template | SignalLoop database | Workspace ID | eCRM endpoint ID | eCRM secret reference |
| --- | --- | --- | --- | --- | --- |
| ARA Global | `docs/operations/examples/ara-global.env.example` | `signalloop_ara_global` | `workspace_ara_global` | `ara-global` | `ara-global-delivery-v1` |
| AI Consulting | `docs/operations/examples/ai-consulting.env.example` | `signalloop_ai_consulting` | `workspace_ai_consulting` | `ai-consulting` | `ai-consulting-delivery-v1` |

Each tracked template can be copied to the deployment environment or to a local ignored `.env.ara-global.example` / `.env.ai-consulting.example` file. Each template includes a separate `POSTGRES_SERVER`, `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` block. Replace those placeholders with the Postgres database issued for that SignalLoop deployment. The eCRM cell databases remain separate from the SignalLoop databases.

After the SignalLoop API is running for a cell, bind the authenticated workspace to the matching eCRM cell:

```powershell
# ARA Global
$env:SIGNALLOOP_API="https://api-signalloop-ara-global.example.com"
$env:SIGNALLOOP_ADMIN_TOKEN="<workspace-admin-token>"
Invoke-RestMethod -Method Put "$env:SIGNALLOOP_API/api/v1/ecrm-installations/binding" `
  -Headers @{ Authorization="Bearer $env:SIGNALLOOP_ADMIN_TOKEN"; "X-Workspace-Id"="workspace_ara_global" } `
  -ContentType "application/json" `
  -Body '{"endpoint_id":"ara-global","secret_reference_id":"ara-global-delivery-v1","capabilities":["SHARED_RECORD","WORKFLOW_EVENT"],"status":"ACTIVE","source_version":1}'

# AI Consulting
$env:SIGNALLOOP_API="https://api-signalloop-ai-consulting.example.com"
$env:SIGNALLOOP_ADMIN_TOKEN="<workspace-admin-token>"
Invoke-RestMethod -Method Put "$env:SIGNALLOOP_API/api/v1/ecrm-installations/binding" `
  -Headers @{ Authorization="Bearer $env:SIGNALLOOP_ADMIN_TOKEN"; "X-Workspace-Id"="workspace_ai_consulting" } `
  -ContentType "application/json" `
  -Body '{"endpoint_id":"ai-consulting","secret_reference_id":"ai-consulting-delivery-v1","capabilities":["SHARED_RECORD","WORKFLOW_EVENT"],"status":"ACTIVE","source_version":1}'
```

The two bindings must resolve to different `POSTGRES_DB` values, different `X-Workspace-Id` values, and different eCRM cell identities. ARA Global uses `cell_ara_global`/`ara-global`; AI Consulting uses `cell_ai_consulting`/`ai-consulting`.

## SignalVoice customer-cell smoke checklist

Run this checklist separately for ARA Global and AI Consulting. Do not reuse a
browser-selected workspace, database, provider credential, or eCRM binding
between the two cells.

1. Confirm the SignalLoop runtime is using the cell-specific environment:
   `POSTGRES_DB`, `DEFAULT_WORKSPACE_ID`, `ECRM_INSTALLATION_ENDPOINTS`, and
   `ECRM_INSTALLATION_SECRET_REFERENCES` match the row in the demo-cell table
   above.
2. Apply migrations with `uv run alembic upgrade head`, then verify the
   authenticated workspace has an active `suite_tenant_workspace_binding` for
   the cell workspace.
3. Provision an active commercial-agent entitlement and activate one
   `VOICE_CONVERSATION` deployment for the workspace. A provider credential by
   itself is not a launch switch.
4. In `Settings -> Providers`, confirm the workspace selects the intended voice
   provider, then smoke-test the stored credential. The credential test only
   proves adapter construction; it does not prove a live call.
5. Create or import one synthetic consented contact with `consent_voice=true`,
   a valid phone number, timezone, campaign, and voice script. Missing or
   ambiguous consent must remain a deny condition.
6. Queue one manual call and run the call worker. A successful provider handoff
   must create a finalized `voice_attempt` agent usage ledger row keyed by the
   call request id and must leave the other demo cell untouched.
7. Complete one post-call processing pass for recording/transcript/summary
   evidence when a recording is available. Local `faster-whisper` is acceptable
   for batch post-call processing; live streaming behavior requires the selected
   provider path.
8. Deliver the resulting shared-record or workflow-event projection to the
   matching eCRM cell, then run reconciliation. `DEGRADED`, `HELD_GAP`, and
   `DEAD_LETTER` are operator action states, not green demo states.
9. Repeat a negative smoke with the other cell's workspace id, endpoint id, or
   secret reference. The request must fail closed and must not project or
   dispatch cross-cell work.

## Delivery and recovery

The authenticated destination is
`POST /api/v1/ecrm-installations/deliveries`. It requires `X-ECRM-Cell-Id`,
`X-ECRM-Cell-Key`, the exact bound `X-Workspace-Id`, a Bearer cell credential,
`X-Correlation-Id`, and `Idempotency-Key`. A receipt is committed before the 202
response. Identical replay returns the same ACK; changed content for the same
key is rejected with 409. The versioned request and ACK example is checked in at
`docs/contracts/signalloop-ecrm-installation-delivery-v1.json`.

The checked-in Compose service `ecrm-installation-projection-worker` runs
continuously. It polls every 10 seconds and claims up to 100 receipts per pass by
default. Override these deployment settings with
`ECRM_INSTALLATION_PROJECTION_POLL_INTERVAL_SECONDS` and
`ECRM_INSTALLATION_PROJECTION_BATCH_SIZE`. Every pass advances due received,
retry, held-gap, and expired in-flight receipts without operator intervention.
The worker publishes `ecrm_installation_projection_worker` heartbeat records for
readiness and error inspection.

Run the continuous worker directly:

```powershell
cd apps/api
uv run python -m app.workers.installation_projection_worker --batch-size 100 --poll-interval 10
```

For an operator-controlled one-shot pass, add `--once`. Optionally restrict
operations to one workspace with `--workspace-id`. This is
an operational filter only; every job derives its workspace and cell from the
receipt. Failed work uses bounded exponential backoff and then dead-letters.
Replay a dead letter through
`POST /api/v1/ecrm-installations/receipts/{id}/replay`.

## Reconciliation and status

Run one source comparison:

```powershell
uv run python -m app.scripts.reconcile_ecrm_installations --workspace-id WS --stream-key installation:primary --source-count 10 --source-checkpoint 10
```

## Binding verification and suspension

Before activation, verify the deployment-owned endpoint and secret-reference IDs resolve to the same immutable eCRM cell; the base URL is an HTTPS origin; the authenticated workspace owns the binding; capabilities are the minimum required; and RevenueOS entitlement gates reads without deleting projection/recovery evidence.

Project `SUSPENDED` immediately and confirm new delivery is denied with no projection advance. Resume only after the authoritative eCRM lifecycle projection is active and reconciliation shows no unresolved version gap.

## Secret rotation

1. Provision a new allowlisted deployment secret reference for the same immutable cell. Never send the secret value through the API.
2. As a workspace admin, call `POST /api/v1/ecrm-installations/binding/credential-rotations` with `X-Workspace-Id` and `{"secret_reference_id":"secret-v2","expected_source_version":1}`.
3. The compare-and-swap accepts only the current version, increments it by one, records a server-owned monotonic `rotated_at`, preserves workspace/cell/key/base URL, and emits `ecrm.installation.credential_rotated` audit evidence. A stale or concurrent loser receives 409; an unprovisioned or cross-cell reference receives 422.
4. After commit, delivery resolves only the new reference. Verify the retired credential fails and the new credential returns a matching ACK, then remove the old deployment secret according to policy.

## Recovery operations

Timeouts and transient responses use bounded retry; repeated client-side destination failures degrade the binding and open its circuit. Projection exceptions use exponential retry and dead-letter after the configured maximum. Replay only through the workspace-scoped admin endpoint with an incident reason, then run reconciliation. A source version gap remains `HELD_GAP` and creates a repair candidate; never silently renumber or copy state from another workspace. A worker crash after the atomic projection/checkpoint/receipt commit is safe to rerun and must not double-apply the side effect.

## Activation boundary

Real eCRM provider endpoints, API keys/secrets, and cloud installation activation were not exercised by local acceptance. Deployment configuration must fail closed when an endpoint, secret allowlist entry, or authority is missing. Do not treat local acknowledgements as proof of live provider or customer readiness.

Mismatches create a deduplicated repair candidate. Inspect receipt status,
checkpoint counts, and repair IDs at `GET /api/v1/ecrm-installations/operations`.
This endpoint contains no event payloads, cell credentials, or secret references.

Treat `DEGRADED`, `HELD_GAP`, and `DEAD_LETTER` as operator action states.
RevenueOS projection state is retained even when its entitlement is disabled so
recovery does not lose evidence; RevenueOS reads remain entitlement-gated.


