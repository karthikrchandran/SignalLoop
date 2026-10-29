"""Local disposable-database gate runner; never connects tests to application data."""

import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import uuid

import psycopg
from psycopg import sql
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
values = dotenv_values(ROOT / ".env")
database = "signalloop_gate_" + uuid.uuid4().hex[:12]
connection = {
    "host": values.get("POSTGRES_SERVER", "localhost"),
    "port": values.get("POSTGRES_PORT", "5432"),
    "user": values["POSTGRES_USER"],
    "password": values["POSTGRES_PASSWORD"],
    "dbname": "postgres",
}
if connection["host"] not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Disposable gate requires the local PostgreSQL cluster")
environment = os.environ.copy()
environment.update({
    "PROJECT_NAME": "SignalLoop",
    "ENVIRONMENT": "local",
    "AUTH_MODE": "local-test",
    "POSTGRES_SERVER": connection["host"],
    "POSTGRES_PORT": str(connection["port"]),
    "POSTGRES_USER": connection["user"],
    "POSTGRES_PASSWORD": connection["password"],
    "POSTGRES_DB": database,
    "FIRST_SUPERUSER": "gate-admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": secrets.token_urlsafe(24),
    "EMAIL_TEST_USER": "gate-user@example.com",
    "EMAILS_FROM_EMAIL": "gate@example.com",
    "SECRET_KEY": secrets.token_urlsafe(48),
    "SMTP_HOST": "127.0.0.1",
    "SMTP_PORT": "1025",
    "SMTP_TLS": "false",
    "SMTP_SSL": "false",
    "REDIS_URL": "redis://127.0.0.1:6379/15",
})
log = ROOT / ".local-services" / f"production-gate-{database}.log"
log.parent.mkdir(exist_ok=True)
scratch = ROOT / ".pytest-gate" / database
scratch.parent.mkdir(parents=True, exist_ok=True)
migrated = "--migrated" in sys.argv[1:]
selectors = [argument for argument in sys.argv[1:] if argument != "--migrated"]
if migrated:
    environment["RUN_TENANT_PG_TESTS"] = "1"
with psycopg.connect(**connection, autocommit=True) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    print(f"Created isolated database {database}", flush=True)
    try:
        command = [
            str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "pytest",
            "-q", "-ra", "--tb=short", "--basetemp", str(scratch),
            *selectors,
        ]
        with log.open("w", encoding="utf-8") as output:
            if migrated:
                subprocess.run(
                    [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m",
                     "alembic", "upgrade", "head"],
                    cwd=ROOT / "apps" / "api", env=environment,
                    stdout=output, stderr=subprocess.STDOUT, check=True,
                )
            result = subprocess.run(
                command, cwd=ROOT / "apps" / "api", env=environment,
                stdout=output, stderr=subprocess.STDOUT,
            )
        print(f"Pytest exit={result.returncode}; log={log}", flush=True)
    finally:
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        shutil.rmtree(scratch, ignore_errors=True)
        print(f"Removed isolated database {database}", flush=True)
sys.exit(result.returncode)
