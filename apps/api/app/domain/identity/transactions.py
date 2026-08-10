"""Short-lived OIDC authorization transactions backed by Redis."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


class TransactionUnavailable(RuntimeError):
    """Raised when the authorization transaction store cannot be reached."""


@dataclass(frozen=True)
class OidcTransaction:
    transaction_id: str
    state_digest: str
    nonce_digest: str
    pkce_verifier: str
    issuer: str
    return_path: str


class OidcTransactionStore:
    def __init__(self, redis: Any, *, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl_seconds = ttl_seconds

    def _key(self, transaction_id: str) -> str:
        return f"oidc:transaction:{transaction_id}"

    async def put(self, transaction: OidcTransaction) -> None:
        try:
            await self._redis.setex(
                self._key(transaction.transaction_id),
                self._ttl_seconds,
                json.dumps(asdict(transaction), separators=(",", ":")),
            )
        except Exception as exc:  # noqa: BLE001
            raise TransactionUnavailable("OIDC transaction store unavailable") from exc

    async def consume(self, transaction_id: str) -> OidcTransaction | None:
        try:
            key = self._key(transaction_id)
            if hasattr(self._redis, "getdel"):
                raw = await self._redis.getdel(key)
            else:
                raw = await self._redis.get(key)
                if raw is not None:
                    await self._redis.delete(key)
        except Exception as exc:  # noqa: BLE001
            raise TransactionUnavailable("OIDC transaction store unavailable") from exc
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return OidcTransaction(**json.loads(raw))
