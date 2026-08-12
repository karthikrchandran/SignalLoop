# Backup and restore test report

Use this template only after an approved isolated recovery rehearsal. Do not
mark the test passed from tool preflight evidence alone.

| Field | Recorded value |
| --- | --- |
| Date and UTC window | |
| Operator and approver | |
| Source database name | |
| Isolated target database name | |
| Backup SHA-256 and size | |
| Preflight evidence file/hash | |
| `pg_dump` / `pg_restore` versions | |
| Expected / observed Alembic head | |
| Tenant-scoped row-count comparison | |
| Object-reference validation result | |
| Restore result and discrepancies | |
| Follow-up owner and due date | |

Attach only secret-free evidence. Never attach connection URLs, credentials,
message bodies, or raw customer exports.
