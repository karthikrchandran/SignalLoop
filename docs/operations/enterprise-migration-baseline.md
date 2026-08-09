# Enterprise migration baseline

This baseline defines the accepted starting point for tenant-isolation migration work. Focused TDD gates are authoritative for each work package. The repositories are not fully green, and later work must not worsen the pre-existing debt listed below or sweep unrelated cleanup into a migration change.

## Source baseline

| Repository | Branch | Starting commit |
| --- | --- | --- |
| eCRM | `codex/enterprise-tenancy` | `035e49ae84f79fb35da70925f61f8ec66c56ffa6` |
| SignalLoop | `codex/revenueos-enterprise` | `8898c25f3470af9da44ea9a6b09f8bdadb7d86c7` |

## Environment and database

- Local Postgres on port `5432`, Redis on port `6379`, and Mailpit on ports `1025` and `8025` were confirmed available during baseline verification.
- SignalLoop API validation used the dedicated database `signalloop_revenueos_enterprise_test`, migrated to Alembic head `psid_20260726`.
- SignalLoop test commands loaded `C:\Users\K.Ramachandran\eMailVoice\.env` without displaying values and overrode only `POSTGRES_DB=signalloop_revenueos_enterprise_test`. From the SignalLoop repository root, use this PowerShell sequence in a clean shell:

  ```powershell
  $revenueOsEnvFile = 'C:\Users\K.Ramachandran\eMailVoice\.env'
  Get-Content -LiteralPath $revenueOsEnvFile | ForEach-Object {
      $revenueOsLine = $_.Trim()
      if ($revenueOsLine -and -not $revenueOsLine.StartsWith('#')) {
          $revenueOsPair = $revenueOsLine -split '=', 2
          if ($revenueOsPair.Count -eq 2) {
              $revenueOsName = $revenueOsPair[0].Trim()
              $revenueOsValue = $revenueOsPair[1].Trim().Trim('"').Trim("'")
              Set-Item -Path "Env:$revenueOsName" -Value $revenueOsValue
          }
      }
  }
  $env:POSTGRES_DB = 'signalloop_revenueos_enterprise_test'
  uv run --project apps/api pytest apps/api/tests/unit/test_tenant_security_helpers.py -q
  ```

  The snippet assigns values directly to the process environment and does not print them.
- `USE_LOCAL_SHARED_RECORDS` remains at its normal/default behavior. It must not be forced to `true` globally to hide remote shared-record integration failures.
- Generated email templates are ignored build artifacts and must not be committed.

## Tenant fixture TDD evidence

### RED

| Package | Command | Expected failure | Duration |
| --- | --- | --- | --- |
| eCRM | `npm test -- src/test/tenant-fixtures.test.ts` | Vitest failed to resolve `./tenant-fixtures`; 1 failed test file, no tests collected. | Vitest 2.22s; 5.1s wall time |
| SignalLoop API | `uv run --project apps/api pytest apps/api/tests/unit/test_tenant_security_helpers.py -q` | Collection failed with `ModuleNotFoundError: No module named 'tests.utils.tenant_security'`. | pytest 0.73s; 8.8s wall time |

### GREEN

| Package | Command | Result | Duration |
| --- | --- | --- | --- |
| eCRM | `npm test -- src/test/tenant-fixtures.test.ts` | 2 tests passed in 1 test file, including repeat-call determinism. | Vitest 2.91s |
| eCRM | `npm run typecheck` | Passed. | 6.4s wall time |
| eCRM | `npx eslint src/test/tenant-fixtures.ts src/test/tenant-fixtures.test.ts --max-warnings=0` | Passed with no lint errors. | 7.2s wall time |
| SignalLoop API | `uv run --project apps/api pytest apps/api/tests/unit/test_tenant_security_helpers.py -q` | 2 tests passed, including namespace isolation and repeat-call determinism. | pytest 0.02s; 10.3s wall time including clean-shell environment loading |
| SignalLoop API | `uv run --project apps/api ruff check apps/api/tests/utils/tenant_security.py apps/api/tests/unit/test_tenant_security_helpers.py` | All checks passed. | 1.6s wall time |
| SignalLoop API | `uv run --project apps/api mypy --config-file apps/api/pyproject.toml apps/api/tests/utils/tenant_security.py apps/api/tests/unit/test_tenant_security_helpers.py` | No issues found in 2 source files. | 6.5s wall time |

The helpers use deterministic synthetic identifiers and reserved `example.com` contact addresses. SignalLoop callers supply a per-scenario namespace so session-scoped tests do not reuse workspace primary keys. The helpers contain no production phone numbers, credentials, or customer data.

## Accepted pre-existing failures

- eCRM `npm run gate`: typecheck passed, lint passed, and tests reported 315 passed with 1 failed. The known date-sensitive failure is `src/server/reports/queries.test.ts`, `Upcoming follow-ups`, which expected 2 and received 1. The chained build step did not run because the test step failed.
- SignalLoop web `npm run build`: passed.
- SignalLoop API full baseline on `signalloop_revenueos_enterprise_test`: 390 passed and 23 failed. Failures are primarily shared-record cutover/source-test drift involving current remote shared-record behavior and `ECRM_SHARED_API_TOKEN`.
- SignalLoop full Ruff baseline: 68 existing errors.
- SignalLoop full mypy baseline: 559 errors in 61 files.

These full-suite results establish known debt; they do not represent a full-green claim. Each migration package must pass its focused checks and must not increase the documented failure counts.
