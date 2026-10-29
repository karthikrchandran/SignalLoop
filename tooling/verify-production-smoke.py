"""Verify the production bundle and API on a newly migrated disposable database."""

import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
import uuid

import httpx
import psycopg
from dotenv import dotenv_values
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
values = dotenv_values(ROOT / ".env")
database = "signalloop_smoke_" + uuid.uuid4().hex[:12]
connection = {
    "host": values.get("POSTGRES_SERVER", "localhost"),
    "port": values.get("POSTGRES_PORT", "5432"),
    "user": values["POSTGRES_USER"],
    "password": values["POSTGRES_PASSWORD"],
    "dbname": "postgres",
}
if connection["host"] not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Production smoke requires the local PostgreSQL cluster")
for port in (18017, 14177):
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Smoke port {port} is already occupied; no existing process was touched")
environment = os.environ.copy()
environment.update({
    "PROJECT_NAME": "SignalLoop",
    "ENVIRONMENT": "production",
    "AUTH_MODE": "oidc",
    "POSTGRES_SERVER": connection["host"],
    "POSTGRES_PORT": str(connection["port"]),
    "POSTGRES_USER": connection["user"],
    "POSTGRES_PASSWORD": connection["password"],
    "POSTGRES_DB": database,
    "FIRST_SUPERUSER": "gate-admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": secrets.token_urlsafe(24),
    "EMAILS_FROM_EMAIL": "gate@example.com",
    "SECRET_KEY": secrets.token_urlsafe(48),
    "REDIS_URL": "redis://127.0.0.1:6379/15",
    "FRONTEND_HOST": "http://127.0.0.1:14177",
    "BACKEND_CORS_ORIGINS": '["http://127.0.0.1:14177"]',
    "USE_ECRM_SHARED_RECORDS": "false",
    "USE_LOCAL_SHARED_RECORDS": "true",
    "VITE_API_URL": "http://127.0.0.1:18017",
    "VITE_AUTH_MODE": "oidc",
})
python = str(ROOT / ".venv" / "Scripts" / "python.exe")
log_path = ROOT / ".local-services" / "production-smoke.log"
log_path.parent.mkdir(exist_ok=True)


def run(command, cwd, output):
    subprocess.run(command, cwd=cwd, env=environment, stdout=output,
                   stderr=subprocess.STDOUT, check=True)


def ready(url, process):
    for _ in range(90):
        if process.poll() is not None:
            raise RuntimeError("Owned smoke server exited before readiness")
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Owned smoke server did not become ready")


with psycopg.connect(**connection, autocommit=True) as admin:
    admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    processes = []
    try:
        with log_path.open("w", encoding="utf-8") as output:
            run([python, "-m", "alembic", "upgrade", "head"], ROOT / "apps" / "api", output)
            run(["npm.cmd", "--workspace", "frontend", "run", "build"], ROOT, output)
            server = subprocess.Popen(
                [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                 "--port", "18017", "--no-access-log"],
                cwd=ROOT / "apps" / "api", env=environment, stdout=output, stderr=subprocess.STDOUT,
            )
            processes.append(server)
            ready("http://127.0.0.1:18017/api/v1/utils/health-check/", server)
            bootstrap = """
from datetime import timedelta
from sqlmodel import Session, select
from app.core.db import engine
from app.models import User
from app.domain.identity.sessions import create_session
from app.domain.shared_records.repository import PlatformSharedRepository
with Session(engine) as session:
    user = session.exec(select(User).where(User.email == 'gate-admin@example.com')).one()
    token = create_session(session, user=user, ttl=timedelta(minutes=10))
    repo = PlatformSharedRepository(session)
    for label in ('One', 'Two'):
        repo.upsert_contact(
            workspace_id='default', external_key='production-gate-' + label,
            display_name='Gate ' + label, first_name='Gate', last_name=label,
            email='gate-' + label.lower() + '@example.com', company_name='Gate Example',
            parent_account_id=None, source_app='production-gate', source_record_id=label,
        )
    session.commit()
    print(token)
"""
            session = subprocess.run(
                [python, "-c", bootstrap], cwd=ROOT / "apps" / "api", env=environment,
                capture_output=True, text=True, check=True,
            )
            environment["GATE_SESSION"] = session.stdout.strip()
            preview = subprocess.Popen(
                [str(ROOT / "node_modules" / ".bin" / "vite.cmd"), "preview",
                 "--host", "127.0.0.1", "--port", "14177", "--strictPort"],
                cwd=ROOT / "apps" / "web", env=environment, stdout=output, stderr=subprocess.STDOUT,
            )
            processes.append(preview)
            ready("http://127.0.0.1:14177/login", preview)
            run(["node", str(ROOT / "tooling" / "production-smoke.cjs")], ROOT, output)
        print("PASS: migrated disposable DB, production API and bundle browser smoke")
    finally:
        for process in reversed(processes):
            if process.poll() is not None:
                continue
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "function Stop-OwnedTree([int]$processId) { "
                 "Get-CimInstance Win32_Process -Filter \"ParentProcessId = $processId\" "
                 "| ForEach-Object { Stop-OwnedTree $_.ProcessId }; "
                 "Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }; "
                 f"Stop-OwnedTree {process.pid}"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            process.wait(timeout=15)
        admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        print(f"Removed smoke database {database} and owned processes")
