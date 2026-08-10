"""Short-lived callback correlation tokens for provider dispatch races."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def mint_correlation_token(
    call_session_id: uuid.UUID,
    signing_key: str,
    *,
    expires_at: int,
) -> str:
    payload = json.dumps(
        {"session": str(call_session_id), "exp": expires_at, "nonce": secrets.token_urlsafe(16)},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def verify_correlation_token(token: str, signing_key: str) -> uuid.UUID | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(signing_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            return None
        return uuid.UUID(str(payload["session"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def utc_from_timestamp(value: int) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)
