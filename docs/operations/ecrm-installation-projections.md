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
