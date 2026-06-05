#!/usr/bin/env python3
"""Seed local demo provider selections.

Usage from repo root:
    uv run python tooling/seed_demo_providers.py

Override workspace:
    $env:DEMO_WORKSPACE_ID="my-ws"
    uv run python tooling/seed_demo_providers.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"


def _load_dotenv() -> None:
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8001").rstrip("/")
WS_ID = os.getenv("DEMO_WORKSPACE_ID", "default")
LOGIN_URL = f"{API_BASE}/api/v1/login/access-token"
SELECTION_URL = f"{API_BASE}/api/v1/workspaces/{WS_ID}/provider-selection"

SELECTIONS = [
    {"capability": "email", "provider": "smtp"},
    {"capability": "llm", "provider": "ollama_local"},
    {"capability": "stt", "provider": "faster_whisper_local"},
]


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def _request_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> dict:
    req = request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=10) as resp:
            data = resp.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: {exc.code} {detail[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"{method} {url} failed: {exc.reason}") from exc

    return json.loads(data.decode("utf-8"))


def get_token() -> str:
    email = _required_env("FIRST_SUPERUSER")
    password = _required_env("FIRST_SUPERUSER_PASSWORD")
    body = parse.urlencode({"username": email, "password": password}).encode()
    data = _request_json(
        LOGIN_URL,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    )
    return data["access_token"]


def seed(token: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Workspace-Id": WS_ID,
        "Content-Type": "application/json",
    }
    for selection in SELECTIONS:
        data = _request_json(
            SELECTION_URL,
            method="PUT",
            headers=headers,
            body=json.dumps(selection).encode("utf-8"),
        )
        print(f"  OK  {data['capability']:8} -> {data['provider']}")


if __name__ == "__main__":
    print(f"Seeding provider selections for workspace '{WS_ID}' at {API_BASE}")
    token = get_token()
    seed(token)
    print("Done. Restart workers for changes to take effect.")
