# Deferred Work

## Deferred from: code review of 1-1-set-up-initial-project-from-starter-template (2026-03-30)

- ~~**Sync `engine.connect()` in async `health_check` blocks event loop** [`apps/api/app/api/routes/utils.py`]~~ — **Resolved 2026-04-02**: Extracted blocking call into `_check_postgres_sync()` helper and awaited it via `anyio.to_thread.run_sync()`, keeping the event loop unblocked.

- ~~**No MongoDB server selection timeout on `MongoConnectionManager.connect()`** [`apps/api/app/infrastructure/db/mongodb/connection.py`]~~ — **Resolved 2026-04-02**: Added `serverSelectionTimeoutMS=5000` to `AsyncIOMotorClient` constructor for faster startup failure detection.
