# eCRM installation projections

SignalLoop binds each authenticated workspace to one eCRM cell through
`ecrm_installation_binding`. The binding is server-owned: request bodies, query
parameters, and worker arguments cannot replace the authenticated workspace or
the stored cell URL, cell identity, or credential reference.

## Configuration

Set the secret named by each binding's `credential_secret_ref`. The built-in
resolver accepts only `env://NAME`; it fails closed when the variable is absent.
Store only the reference, never the credential value. Production secret-manager
adapters implement `SecretResolver` and are injected at deployment time. OIDC
and external CRM connectors remain intentionally inactive.

Apply the database migration before enabling delivery:

```powershell
cd apps/api
uv run alembic upgrade head
```

Create or rotate a binding through `PUT /api/v1/ecrm-installations/binding`
while authenticated as a workspace admin and sending `X-Workspace-Id`. The
response deliberately omits `credential_secret_ref` and all secret values.

## Delivery and recovery

The authenticated destination is
`POST /api/v1/ecrm-installations/deliveries`. It requires `X-ECRM-Cell-Id`, a
Bearer cell credential, and `Idempotency-Key`. A receipt is committed before the
202 response. Identical replay is acknowledged; changed content for the same key
is rejected with 409.

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

Mismatches create a deduplicated repair candidate. Inspect receipt status,
checkpoint counts, and repair IDs at `GET /api/v1/ecrm-installations/operations`.
This endpoint contains no event payloads, cell credentials, or secret references.

Treat `DEGRADED`, `HELD_GAP`, and `DEAD_LETTER` as operator action states.
RevenueOS projection state is retained even when its entitlement is disabled so
recovery does not lose evidence; RevenueOS reads remain entitlement-gated.
