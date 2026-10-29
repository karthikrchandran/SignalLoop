# Tenant backup and isolated restore rehearsal

This procedure produces reviewable recovery evidence without allowing a tool
to restore over the active SignalLoop database. It is an operator-run
rehearsal, not a substitute for provider backup retention or a production
failover plan.

## Native PostgreSQL baseline

Local development uses the existing native PostgreSQL 18 cluster on port `5432`; Docker and a Supabase account are not required. SignalLoop and eCRM may share that server, but must keep separate databases and application credentials. Use matching PostgreSQL 18 backup/restore binaries. Restore into a new database, never over the other application's database.

The optional PostgreSQL 18 Compose volume is independent of native data and of older container volumes. Switching an image or connection string does not migrate existing data. Verify recovery before any major-version change.

## Schema-history drift

An existing table with a missing Alembic revision is a schema/history discrepancy, not a reason to reset the database or blindly stamp `head`. In particular, tests that create current model tables outside Alembic must use disposable databases, not the normal application database.

Rehearse repair on an isolated restore: create a clean reference using the full migration history, compare columns, types, defaults, keys, indexes, checks, functions, triggers, and policies, and validate every new constraint against preserved data. Review data migrations separately. Only reconcile recorded revisions after the repaired schema matches that reference and existing row contents have been verified unchanged. Keep the pre-repair dump, environment backup, repair plan, and verification evidence privately. Re-run application login and authenticated reads before declaring recovery complete.

## Preconditions

- Create a PostgreSQL custom-format logical backup with `pg_dump` and store it
  in an access-controlled, encrypted location.
- Provision an empty recovery database whose name contains `_restore`,
  `_recovery`, or `_isolated`; for example `signalloop_restore_20260812`.
- Put source and recovery connection URLs only in the current process
  environment. Never place them in the command line, evidence JSON, Git, or
  support tickets.
- Install compatible `pg_dump` and `pg_restore` binaries and obtain the
  expected Alembic migration head and optional post-restore row-count JSON.

## Capture preflight evidence

Set `DATABASE_URL` to the source and `RECOVERY_DATABASE_URL` to the empty,
isolated target. The tool validates the tools, the backup artifact, the URL
database names, and the isolation marker. It refuses equal source/target
database names.

```powershell
$env:DATABASE_URL = '<source connection from approved secret store>'
$env:RECOVERY_DATABASE_URL = '<isolated recovery connection from approved secret store>'
uv run python tooling/backup_restore_evidence.py `
  --backup D:\SignalLoopBackups\signalloop-20260812.dump `
  --migration-head p1_lead_discovery_engine_20261010 `
  --row-validation docs\operations\evidence\recovery-row-counts.json `
  --evidence docs\operations\evidence\backup-restore-preflight.json `
  --emit-restore-plan
```

The resulting evidence includes a backup SHA-256, artifact size, PostgreSQL
tool versions, timestamp, migration head, database names, and supplied row
validation counts. It intentionally excludes connection URLs, hosts, users,
and credentials.

## Restore and verify

After a qualified operator reviews the emitted plan and confirms the target is
isolated, run its displayed `pg_restore` command in the same shell. The command
uses `RECOVERY_DATABASE_URL`, includes `--exit-on-error`, and deliberately
omits `--clean`, so it cannot silently drop an existing database.

Then, in the recovery environment only:

1. Apply/verify the expected Alembic head.
2. Query the approved tenant-scoped record counts and compare them to the
   pre-backup counts in `recovery-row-counts.json`.
3. Verify object references resolve without downloading or exposing message
   bodies.
4. Record restore start/end time, operator, query hashes/results, discrepancies,
   and the preflight evidence hash in the recovery test report.

Do not run `pg_restore`, deletion, credential revocation, or provider calls
against the source environment as part of this procedure. A real restore test,
object-store reconciliation, queue/cache deletion, and customer acceptance
remain externally executed operational controls.
